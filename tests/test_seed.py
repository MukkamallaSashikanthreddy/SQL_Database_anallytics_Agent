from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text

from database.seed import seed_database
from app.database import create_readonly_engine, execute_readonly_sql, reflect_schema, get_table_counts


def test_seed_creates_database_file(sample_db):
    assert sample_db.exists()


def test_seed_creates_customers_orders_sales(sample_db):
    engine = create_readonly_engine(sample_db)
    try:
        assert set(inspect(engine).get_table_names()) == {"customers", "orders", "sales"}
    finally:
        engine.dispose()


def test_orders_have_required_id_and_order_date_columns(sample_db):
    schema = reflect_schema(create_readonly_engine(sample_db))
    order_columns = {column["name"] for column in schema["orders"]["columns"]}
    assert {"id", "order_date", "order_id"}.issubset(order_columns)


def test_seed_has_ten_orders(sample_db):
    engine = create_readonly_engine(sample_db)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one() == 10
    finally:
        engine.dispose()


def test_seed_has_six_customers(sample_db):
    engine = create_readonly_engine(sample_db)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM customers")).scalar_one() == 6
    finally:
        engine.dispose()


def test_seed_has_twenty_sales_lines(sample_db):
    engine = create_readonly_engine(sample_db)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM sales")).scalar_one() == 20
    finally:
        engine.dispose()


def test_seed_foreign_keys_reflect(sample_db):
    schema = reflect_schema(create_readonly_engine(sample_db))
    assert schema["orders"]["foreign_keys"][0]["referred_table"] == "customers"
    assert schema["sales"]["foreign_keys"][0]["referred_table"] == "orders"


def test_seed_recreates_tables_on_second_run(sample_db):
    seed_database(sample_db)
    engine = create_readonly_engine(sample_db)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one() == 10
    finally:
        engine.dispose()


def test_database_counts_helper(sample_db):
    engine = create_readonly_engine(sample_db)
    try:
        assert get_table_counts(engine) == {"customers": 6, "orders": 10, "sales": 20}
    finally:
        engine.dispose()


def test_readonly_query_returns_order_count(sample_db):
    result = execute_readonly_sql("SELECT COUNT(*) AS order_count FROM orders LIMIT 2", engine=create_readonly_engine(sample_db))
    assert result["rows"][0]["order_count"] == 10
