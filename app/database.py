"""Safe database helpers used by the analytics agent and dashboard."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH, MAX_RESULT_ROWS, SQLITE_QUERY_TIMEOUT_SECONDS


def connect_readonly(db_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    """Open a SQLite database in read-only mode and enforce query-only access."""
    path = Path(db_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}. Run `python -m database.seed` first.")
    uri = f"{path.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=SQLITE_QUERY_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    deadline = time.monotonic() + SQLITE_QUERY_TIMEOUT_SECONDS
    connection.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    return connection


def execute_readonly_query(
    sql: str,
    db_path: str | Path = DATABASE_PATH,
    *,
    max_rows: int = MAX_RESULT_ROWS,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Execute previously validated SQL and return column names and row dictionaries."""
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    connection = connect_readonly(db_path)
    try:
        cursor = connection.execute(sql)
        columns = [description[0] for description in (cursor.description or [])]
        rows = [dict(row) for row in cursor.fetchmany(max_rows + 1)]
        if len(rows) > max_rows:
            rows = rows[:max_rows]
        return columns, rows
    finally:
        connection.close()


def get_database_schema(db_path: str | Path = DATABASE_PATH) -> str:
    """Return compact schema context for the SQL generation prompt."""
    connection = connect_readonly(db_path)
    try:
        table_rows = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        parts: list[str] = []
        for table_row in table_rows:
            table_name = table_row["name"]
            columns = connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            column_descriptions = [
                f"{column['name']} ({column['type']})" + (" PRIMARY KEY" if column["pk"] else "")
                for column in columns
            ]
            parts.append(f"Table {table_name}: " + ", ".join(column_descriptions))
        return "\n".join(parts)
    finally:
        connection.close()


def get_dashboard_metrics(db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    """Return trusted aggregate metrics for the Streamlit overview."""
    connection = connect_readonly(db_path)
    try:
        order_metrics = connection.execute(
            """
            SELECT COUNT(*) AS order_count,
                   COUNT(DISTINCT customer_id) AS customer_count,
                   MIN(order_date) AS first_order_date,
                   MAX(order_date) AS last_order_date
            FROM orders
            WHERE status != 'Cancelled'
            """
        ).fetchone()
        revenue = connection.execute(
            """
            SELECT COALESCE(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 0) AS revenue,
                   COALESCE(SUM(oi.quantity * p.unit_cost), 0) AS cost
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN products p ON p.product_id = oi.product_id
            WHERE o.status != 'Cancelled'
            """
        ).fetchone()
        return {
            **dict(order_metrics),
            "revenue": float(revenue["revenue"]),
            "cost": float(revenue["cost"]),
            "gross_profit": float(revenue["revenue"] - revenue["cost"]),
        }
    finally:
        connection.close()
