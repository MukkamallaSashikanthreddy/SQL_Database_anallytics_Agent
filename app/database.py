"""SQLite connectivity, schema reflection, and bounded read-only execution."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import MAX_RESULT_ROWS, database_path


def _user_table_names(engine: Engine) -> list[str]:
    """Return user-created tables, excluding SQLite's internal metadata tables."""
    return sorted(
        name for name in inspect(engine).get_table_names()
        if not name.lower().startswith("sqlite_")
    )


def build_readonly_url(path: str | Path | None = None) -> str:
    """Build a SQLite URI URL with read-only mode enabled."""
    db_file = Path(path) if path else database_path()
    db_file = db_file.resolve()
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_file}. Run `python -m database.seed` first.")
    return f"sqlite:///file:{quote(db_file.as_posix())}?mode=ro&uri=true"


def create_readonly_engine(path: str | Path | None = None) -> Engine:
    return create_engine(
        build_readonly_url(path),
        connect_args={"timeout": 30, "check_same_thread": False},
        pool_pre_ping=True,
    )


def reflect_schema(engine: Engine | None = None) -> dict[str, Any]:
    """Reflect every user table, its columns, primary keys, and foreign keys."""
    owned = engine is None
    engine = engine or create_readonly_engine()
    try:
        inspector = inspect(engine)
        tables: dict[str, Any] = {}
        for table_name in _user_table_names(engine):
            primary_key_columns = set(
                (inspector.get_pk_constraint(table_name) or {}).get("constrained_columns") or []
            )
            columns = inspector.get_columns(table_name)
            tables[table_name] = {
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column.get("nullable", True),
                        "primary_key": column["name"] in primary_key_columns,
                    }
                    for column in columns
                ],
                "foreign_keys": inspector.get_foreign_keys(table_name),
            }
        return tables
    finally:
        if owned:
            engine.dispose()


def format_schema(schema: dict[str, Any]) -> str:
    """Format reflected table metadata as readable model context."""
    lines: list[str] = []
    for name, details in schema.items():
        column_parts = []
        for column in details["columns"]:
            flags = []
            if column.get("primary_key"):
                flags.append("PRIMARY KEY")
            if not column.get("nullable", True):
                flags.append("NOT NULL")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            column_parts.append(f"{column['name']} ({column['type']}){suffix}")
        lines.append(f"TABLE {name}: {', '.join(column_parts)}")
        for fk in details.get("foreign_keys", []):
            lines.append(
                f"  FOREIGN KEY ({', '.join(fk.get('constrained_columns', []))}) "
                f"REFERENCES {fk.get('referred_table')}({', '.join(fk.get('referred_columns', []))})"
            )
    return "\n".join(lines)


def execute_readonly_sql(sql: str, *, engine: Engine | None = None) -> dict[str, Any]:
    """Execute a validated SQL query and return bounded rows and metadata."""
    owned = engine is None
    engine = engine or create_readonly_engine()
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(row._mapping) for row in result.fetchmany(MAX_RESULT_ROWS + 1)]
            truncated = len(rows) > MAX_RESULT_ROWS
            rows = rows[:MAX_RESULT_ROWS]
            return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}
    except SQLAlchemyError:
        raise
    finally:
        if owned:
            engine.dispose()


def get_table_counts(engine: Engine | None = None) -> dict[str, int]:
    """Return row counts for every user table in the active database."""
    owned = engine is None
    engine = engine or create_readonly_engine()
    try:
        counts: dict[str, int] = {}
        preparer = engine.dialect.identifier_preparer
        with engine.connect() as connection:
            for table_name in _user_table_names(engine):
                quoted_name = preparer.quote(table_name)
                counts[table_name] = int(
                    connection.execute(text(f"SELECT COUNT(*) FROM {quoted_name}")).scalar_one()
                )
        return counts
    finally:
        if owned:
            engine.dispose()
