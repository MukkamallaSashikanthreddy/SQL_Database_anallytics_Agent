"""Safe CSV/Excel-to-SQLite import helpers for the Streamlit data workspace."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect

from app.config import database_path

MAX_IMPORT_ROWS = 100_000
MAX_IMPORT_COLUMNS = 100
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def normalize_identifier(value: str, *, fallback: str = "table") -> str:
    """Convert a user-supplied table/column label into a conservative SQLite name."""
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    if not value:
        value = fallback
    if not value[0].isalpha():
        value = f"{fallback}_{value}"
    value = value[:63].rstrip("_")
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError("Use names containing letters, numbers, and underscores only.")
    if value.startswith("sqlite_"):
        raise ValueError("Names beginning with 'sqlite_' are reserved by SQLite.")
    return value


def prepare_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Validate dimensions and normalize column names before importing."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("The uploaded data could not be read as a tabular dataset.")
    if data.empty:
        raise ValueError("The uploaded dataset has no data rows.")
    if len(data.columns) == 0:
        raise ValueError("The uploaded dataset has no columns.")
    if len(data) > MAX_IMPORT_ROWS:
        raise ValueError(f"The dataset contains more than {MAX_IMPORT_ROWS:,} rows. Please reduce the file size.")
    if len(data.columns) > MAX_IMPORT_COLUMNS:
        raise ValueError(f"The dataset contains more than {MAX_IMPORT_COLUMNS} columns.")

    normalized_columns = [
        normalize_identifier(str(column), fallback=f"column_{index + 1}")
        for index, column in enumerate(data.columns)
    ]
    if len(set(normalized_columns)) != len(normalized_columns):
        raise ValueError(
            "Two or more column names become identical after cleanup. Rename those columns in your file and upload again."
        )

    result = data.copy()
    result.columns = normalized_columns
    for column in result.columns:
        # SQLite cannot persist nested Python objects as ordinary scalar cells.
        non_null = result[column].dropna()
        if not non_null.empty and non_null.map(lambda value: isinstance(value, (dict, list, tuple, set))).any():
            raise ValueError(f"Column '{column}' contains nested values. Flatten it before importing.")
    return result


def import_dataframe(
    data: pd.DataFrame,
    table_name: str,
    *,
    db_path: str | Path | None = None,
) -> dict[str, object]:
    """Append a new table to the active SQLite database without overwriting data."""
    clean_data = prepare_dataframe(data)
    safe_table_name = normalize_identifier(table_name, fallback="uploaded_data")
    target = Path(db_path) if db_path else database_path()
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Build the writable connection only for this import action; agent queries
    # continue to use the independent SQLite read-only connection.
    engine = create_engine(f"sqlite:///{target.as_posix()}", future=True)
    try:
        existing_tables = set(inspect(engine).get_table_names())
        if safe_table_name in existing_tables:
            raise ValueError(
                f"A table named '{safe_table_name}' already exists. Choose a different table name; existing data is never overwritten."
            )
        with engine.begin() as connection:
            clean_data.to_sql(
                safe_table_name,
                connection,
                if_exists="fail",
                index=False,
                chunksize=1000,
            )
        return {
            "table_name": safe_table_name,
            "rows_imported": int(len(clean_data)),
            "columns_imported": int(len(clean_data.columns)),
            "column_names": list(clean_data.columns),
        }
    finally:
        engine.dispose()
