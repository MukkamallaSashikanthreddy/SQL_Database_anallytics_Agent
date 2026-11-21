from __future__ import annotations

import sqlite3

import pytest

from app.database import connect_readonly, execute_readonly_query, get_database_schema, get_dashboard_metrics
from database.seed import seed_database


def test_seed_creates_expected_tables_and_data(sample_db):
    with sqlite3.connect(sample_db) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"customers", "products", "orders", "order_items"}.issubset(tables)
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables if table != "sqlite_sequence"}
    assert counts["customers"] == 120
    assert counts["products"] == 18
    assert counts["orders"] == 720
    assert counts["order_items"] >= counts["orders"]


def test_seed_is_idempotent(sample_db):
    seed_database(sample_db)
    with sqlite3.connect(sample_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 720


def test_database_schema_contains_relationship_tables(sample_db):
    schema = get_database_schema(sample_db)
    assert "Table customers" in schema
    assert "Table orders" in schema
    assert "Table order_items" in schema


def test_readonly_query_returns_rows(sample_db):
    columns, rows = execute_readonly_query("SELECT customer_id, region FROM customers ORDER BY customer_id LIMIT 3", sample_db)
    assert columns == ["customer_id", "region"]
    assert len(rows) == 3
    assert rows[0]["customer_id"] == 1


def test_readonly_connection_rejects_write(sample_db):
    connection = connect_readonly(sample_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM customers")
    finally:
        connection.close()


def test_dashboard_metrics_are_nonnegative(sample_db):
    metrics = get_dashboard_metrics(sample_db)
    assert metrics["order_count"] > 0
    assert metrics["customer_count"] > 0
    assert metrics["revenue"] > 0
    assert metrics["gross_profit"] >= 0
