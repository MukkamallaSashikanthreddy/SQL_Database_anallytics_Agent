from __future__ import annotations

import pytest

langgraph = pytest.importorskip("langgraph")

from app.graph import run_agent


def test_demo_agent_runs_against_sample_database(sample_db):
    result = run_agent("Which product categories generated the most revenue?", db_path=str(sample_db))
    assert result["status"] == "completed"
    assert result["mode"] == "demo"
    assert result["rows"]
    assert "category" in [column.lower() for column in result["columns"]]
    assert "LIMIT" in result["validated_sql"].upper()


def test_demo_agent_counts_orders(sample_db):
    result = run_agent("How many orders were placed?", db_path=str(sample_db))
    assert result["status"] == "completed"
    assert result["rows"][0]["order_count"] > 0


def test_agent_blocks_mutation_request(sample_db):
    from app.security import SQLSafetyError
    with pytest.raises(SQLSafetyError):
        run_agent("Delete all customer records", db_path=str(sample_db))
