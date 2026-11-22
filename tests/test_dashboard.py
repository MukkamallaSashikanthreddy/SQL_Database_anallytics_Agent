from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.dashboard import build_result_frame, chart_suggestion, execution_telemetry, sanitize_error


def test_build_dataframe_from_query_result():
    frame = build_result_frame({"columns": ["region", "revenue"], "rows": [{"region": "South", "revenue": 100.0}]})
    assert list(frame.columns) == ["region", "revenue"]
    assert frame.iloc[0]["revenue"] == 100.0


def test_chart_suggestion_uses_pie_for_small_category_count():
    figure = chart_suggestion(pd.DataFrame({"region": ["South", "North"], "revenue": [100, 90]}))
    assert isinstance(figure, go.Figure)
    assert figure.data[0].type == "pie"


def test_chart_suggestion_uses_bar_for_many_categories():
    frame = pd.DataFrame({"product": [f"P{i}" for i in range(10)], "revenue": list(range(10))})
    figure = chart_suggestion(frame)
    assert figure is not None
    assert figure.data[0].type == "bar"


def test_chart_suggestion_uses_line_for_month_dimension():
    frame = pd.DataFrame({"month": ["2026-01", "2026-02"], "revenue": [100, 120]})
    figure = chart_suggestion(frame)
    assert figure is not None
    assert figure.data[0].type == "scatter"


def test_chart_suggestion_skips_id_only_dimension():
    frame = pd.DataFrame({"customer_id": [1, 2], "revenue": [100, 150]})
    assert chart_suggestion(frame) is None


def test_chart_suggestion_skips_text_only_data():
    frame = pd.DataFrame({"region": ["South", "North"], "city": ["Chennai", "Delhi"]})
    assert chart_suggestion(frame) is None


def test_chart_suggestion_skips_single_column_result():
    assert chart_suggestion(pd.DataFrame({"order_count": [10]})) is None


def test_execution_telemetry_contains_core_fields():
    result = execution_telemetry({"status": "success", "retry_count": 1, "referenced_tables": ["orders"], "db_result": {"row_count": 3, "truncated": False}, "guardrail_status": "passed"})
    assert result["status"] == "success"
    assert result["row_count"] == 3
    assert result["retry_count"] == 1


def test_error_sanitizer_redacts_api_key_text():
    result = sanitize_error("ProviderError: GOOGLE_API_KEY=abc123 request failed")
    assert "abc123" not in result
    assert "credentials" in result


def test_error_sanitizer_preserves_safe_error():
    assert sanitize_error("SQL syntax error near SELECT") == "SQL syntax error near SELECT"
