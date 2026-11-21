"""Result summaries and chart recommendations."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def result_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def choose_chart(data: pd.DataFrame):
    """Choose a simple chart only when the returned result has a useful shape."""
    if data.empty or len(data.columns) < 2:
        return None, "No chart suggestion for this result."

    numeric_columns = list(data.select_dtypes(include="number").columns)
    categorical_columns = [
        column for column in data.columns
        if column not in numeric_columns
        and not column.lower().endswith("_id")
        and column.lower() not in {"id", "index"}
    ]
    if not numeric_columns or not categorical_columns:
        return None, "No chart suggestion: the result needs a category/date and a numeric measure."

    x_column = categorical_columns[0]
    y_column = numeric_columns[0]
    normalized_name = x_column.lower()

    if "date" in normalized_name or "month" in normalized_name or "year" in normalized_name:
        fig = px.line(data, x=x_column, y=y_column, markers=True, title=f"{y_column} over {x_column}")
    elif data[x_column].nunique(dropna=True) <= 8:
        fig = px.pie(data, names=x_column, values=y_column, title=f"{y_column} by {x_column}")
    else:
        fig = px.bar(data, x=x_column, y=y_column, title=f"{y_column} by {x_column}")
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=55, b=20))
    return fig, f"Suggested chart: {y_column} by {x_column}."


def format_currency(value: float) -> str:
    return f"₹{value:,.0f}"
