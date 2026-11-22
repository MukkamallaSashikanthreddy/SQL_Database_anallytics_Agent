from __future__ import annotations

import pytest

pytest.importorskip("sqlglot", reason="SQLGlot is installed from requirements.txt")
from app.security import SQLValidationError, validate_sql


@pytest.mark.parametrize("sql", [
    "SELECT * FROM orders",
    "SELECT id, order_date FROM orders ORDER BY order_date DESC LIMIT 5",
    "SELECT region, COUNT(*) AS n FROM customers GROUP BY region",
    "SELECT o.order_id, c.customer_name FROM orders o JOIN customers c ON c.customer_id=o.customer_id",
    "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent LIMIT 10",
    "SELECT category, SUM(quantity) FROM sales GROUP BY category",
    "SELECT COUNT(*) FROM sales WHERE category = 'Audio'",
    "SELECT strftime('%Y-%m', order_date) AS month FROM orders GROUP BY month",
])
def test_accepts_read_only_sql(sql):
    result = validate_sql(sql)
    assert result.sql.upper().startswith(("SELECT", "WITH"))
    assert result.tables
    assert "LIMIT" in result.sql.upper()


@pytest.mark.parametrize("sql", [
    "DELETE FROM orders",
    "UPDATE orders SET status='Cancelled'",
    "INSERT INTO orders(order_id) VALUES('X')",
    "DROP TABLE orders",
    "ALTER TABLE orders ADD COLUMN secret TEXT",
    "CREATE TABLE secrets(id INTEGER)",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM secrets",
    "SELECT * FROM orders; DELETE FROM orders",
    "SELECT * FROM orders INTO OUTFILE 'x'",
    "SELECT load_extension('evil') FROM orders",
    "SELECT readfile('/etc/passwd') FROM orders",
    "PRAGMA table_info(orders)",
])
def test_rejects_unsafe_sql(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


def test_adds_limit_when_missing():
    result = validate_sql("SELECT order_id FROM orders")
    assert result.limit_added_or_clamped is True
    assert "LIMIT 1000" in result.sql.upper()


def test_clamps_limit_above_maximum():
    result = validate_sql("SELECT order_id FROM orders LIMIT 999999")
    assert result.limit_added_or_clamped is True
    assert "LIMIT 1000" in result.sql.upper()


def test_preserves_smaller_limit():
    result = validate_sql("SELECT order_id FROM orders LIMIT 20")
    assert result.limit_added_or_clamped is False
    assert "LIMIT 20" in result.sql.upper()


def test_rejects_negative_limit():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT order_id FROM orders LIMIT -1")


def test_rejects_multiple_statements():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT * FROM orders; SELECT * FROM sales")


def test_rejects_qualified_external_schema():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT * FROM main.orders")


def test_validate_sql_accepts_explicitly_reflected_user_table():
    result = validate_sql("SELECT region, SUM(revenue) AS total FROM monthly_sales GROUP BY region", allowed_tables={"monthly_sales"})
    assert result.tables == ("monthly_sales",)


def test_validate_sql_rejects_table_not_in_reflected_schema():
    with pytest.raises(SQLValidationError, match="not available"):
        validate_sql("SELECT * FROM secret_table", allowed_tables={"monthly_sales"})
