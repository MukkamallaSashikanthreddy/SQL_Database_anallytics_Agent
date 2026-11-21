from __future__ import annotations

import pytest

from app.security import SQLSafetyError, validate_readonly_sql, validate_user_question


def test_accepts_select_and_adds_limit():
    result = validate_readonly_sql("SELECT region, COUNT(*) AS n FROM customers GROUP BY region")
    assert "LIMIT 1000" in result.sql.upper()
    assert result.tables == ("customers",)
    assert result.row_limit_added is True


def test_accepts_cte():
    query = "WITH totals AS (SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id) SELECT * FROM totals"
    result = validate_readonly_sql(query)
    assert "WITH" in result.sql.upper()
    assert result.tables == ("orders",)


@pytest.mark.parametrize("query", [
    "DELETE FROM customers",
    "UPDATE customers SET region='West'",
    "INSERT INTO customers VALUES (999, 'x', 'x', 'x', 'x', '2026-01-01')",
    "DROP TABLE customers",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM secrets",
    "SELECT load_extension('x') FROM customers",
    "SELECT * FROM customers; DELETE FROM customers",
])
def test_rejects_unsafe_sql(query):
    with pytest.raises(SQLSafetyError):
        validate_readonly_sql(query)


def test_clamps_large_limit():
    result = validate_readonly_sql("SELECT * FROM customers LIMIT 999999")
    assert "LIMIT 1000" in result.sql.upper()
    assert result.row_limit_added is True


def test_rejects_mutating_natural_language_request():
    with pytest.raises(SQLSafetyError):
        validate_user_question("Delete all orders from the database")


def test_accepts_analytics_question():
    validate_user_question("Which region generated the highest revenue?")


def test_rejects_empty_question():
    with pytest.raises(SQLSafetyError):
        validate_user_question("   ")
