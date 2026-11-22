from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="LangGraph is installed from requirements.txt")
pytest.importorskip("sqlglot", reason="SQLGlot is installed from requirements.txt")

from app.graph import extract_sql, run_query


class FakeGemini:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        text = self.responses.pop(0)
        return type("AIMessage", (), {"content": text})()


def test_extract_sql_removes_markdown_fence():
    assert extract_sql("```sql\nSELECT * FROM orders\n```") == "SELECT * FROM orders"


def test_extract_sql_removes_sql_prefix():
    assert extract_sql("SQL: SELECT * FROM orders") == "SELECT * FROM orders"


def test_langgraph_executes_live_database_query(sample_db, monkeypatch):
    from app import graph
    engine_factory = lambda: graph.create_readonly_engine(sample_db)
    model = FakeGemini(["SELECT COUNT(*) AS order_count FROM orders"])
    result = run_query("How many orders were placed?", model=model, engine_factory=engine_factory)
    assert result["status"] == "success"
    assert result["db_result"]["rows"][0]["order_count"] == 10
    assert result["retry_count"] == 0


def test_langgraph_retries_after_database_error(sample_db, monkeypatch):
    from app import graph
    engine_factory = lambda: graph.create_readonly_engine(sample_db)
    model = FakeGemini([
        "SELECT missing_column FROM orders",
        "SELECT COUNT(*) AS order_count FROM orders",
    ])
    result = run_query("How many orders were placed?", model=model, engine_factory=engine_factory)
    assert result["status"] == "success"
    assert result["retry_count"] == 1
    assert result["db_result"]["rows"][0]["order_count"] == 10
    assert result["self_correction_history"]


def test_langgraph_blocks_input_before_schema_or_model(sample_db, monkeypatch):
    from app import graph
    model = FakeGemini(["SELECT 1 FROM orders"])
    result = run_query("DROP TABLE orders", model=model, engine_factory=lambda: graph.create_readonly_engine(sample_db))
    assert result["status"] == "blocked"
    assert model.prompts == []


def test_langgraph_does_not_execute_invalid_sql(sample_db, monkeypatch):
    from app import graph
    # Use the fixture database. Without this injected factory, the test would
    # accidentally connect to the developer's default database path instead.
    engine_factory = lambda: graph.create_readonly_engine(sample_db)
    model = FakeGemini(["DELETE FROM orders"] * 4)
    result = run_query(
        "Show orders",
        model=model,
        engine_factory=engine_factory,
    )
    assert result["status"] == "failed"
    assert result.get("db_result") is None
    assert result["retry_count"] == 4
    assert len(model.prompts) == 4


def test_build_graph_returns_compiled_invokable_graph(sample_db):
    # LangGraph returns a CompiledStateGraph. It is executed through .invoke()
    # or .stream(); the compiled graph object itself is not directly callable.
    from app.graph import build_graph
    from app import graph

    compiled_graph = build_graph(
        model=FakeGemini(["SELECT 1 FROM orders"]),
        engine_factory=lambda: graph.create_readonly_engine(sample_db),
    )
    assert callable(compiled_graph.invoke)
    assert callable(compiled_graph.stream)
