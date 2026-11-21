from __future__ import annotations

import pandas as pd

from app.analytics import choose_chart, result_dataframe


def test_result_dataframe_converts_rows():
    data = result_dataframe([{"region": "South", "revenue": 120.5}])
    assert list(data.columns) == ["region", "revenue"]
    assert data.iloc[0]["region"] == "South"


def test_choose_chart_for_categories_and_numeric_measure():
    data = pd.DataFrame({"region": ["North", "South"], "revenue": [100, 150]})
    figure, note = choose_chart(data)
    assert figure is not None
    assert "Suggested chart" in note


def test_choose_chart_skips_text_only_data():
    data = pd.DataFrame({"customer": ["A", "B"], "city": ["Chennai", "Pune"]})
    figure, note = choose_chart(data)
    assert figure is None
    assert "No chart" in note


def test_choose_chart_for_monthly_data():
    data = pd.DataFrame({"month": ["2026-01", "2026-02"], "revenue": [100, 150]})
    figure, _ = choose_chart(data)
    assert figure is not None
    assert figure.data[0].type == "scatter"
