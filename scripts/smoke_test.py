"""No-API smoke test of the data, SQL safety, execution and chart pipeline."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.analytics import choose_chart, result_dataframe
from app.database import execute_readonly_query, get_database_schema
from app.demo_planner import demo_sql
from app.security import validate_readonly_sql
from database.seed import seed_database


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sql-agent-smoke-") as folder:
        db_path = Path(folder) / "smoke.db"
        seed_database(db_path)
        schema = get_database_schema(db_path)
        assert "customers" in schema and "order_items" in schema

        question = "Which product categories generated the most revenue?"
        raw_sql = demo_sql(question)
        validated = validate_readonly_sql(raw_sql)
        columns, rows = execute_readonly_query(validated.sql, db_path)
        assert rows, "Expected the sample analytics query to return rows."
        assert "category" in [column.lower() for column in columns]
        frame = result_dataframe(rows)
        figure, note = choose_chart(frame)
        assert figure is not None, note

        print("SMOKE TEST PASSED")
        print(f"Database tables discovered: {len([line for line in schema.splitlines() if line.startswith('Table ')])}")
        print(f"Validated tables used: {', '.join(validated.tables)}")
        print(f"Result rows: {len(rows)}")
        print(f"Chart: {note}")


if __name__ == "__main__":
    main()
