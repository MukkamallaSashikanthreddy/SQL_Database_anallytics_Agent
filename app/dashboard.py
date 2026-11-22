"""Pure dashboard helpers, separated from Streamlit for easy testing."""
from __future__ import annotations

from typing import Any
import pandas as pd
import plotly.express as px

ID_COLUMN_NAMES = {"id", "order_id", "customer_id", "sale_id", "product_id"}


def build_result_frame(db_result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(db_result.get("rows", []), columns=db_result.get("columns", []))


def chart_suggestion(data: pd.DataFrame):
    """Return an appropriate Plotly figure, or None for unsuitable result shapes."""
    if data.empty or len(data.columns) < 2:
        return None
    numeric = list(data.select_dtypes(include="number").columns)
    dimensions = [
        column for column in data.columns
        if column not in numeric and column.lower() not in ID_COLUMN_NAMES
        and not column.lower().endswith("_id")
    ]
    if not numeric or not dimensions:
        return None

    x = dimensions[0]
    y = numeric[0]
    name = x.lower()
    if any(token in name for token in ("date", "month", "year", "period", "week")):
        figure = px.line(data, x=x, y=y, markers=True, title=f"{y} over {x}")
    elif data[x].nunique(dropna=True) <= 8:
        figure = px.pie(data, names=x, values=y, title=f"{y} by {x}", hole=0.35)
    else:
        figure = px.bar(data, x=x, y=y, title=f"{y} by {x}")
    figure.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=55, b=20))
    return figure


def execution_telemetry(state: dict[str, Any]) -> dict[str, Any]:
    result = state.get("db_result", {})
    return {
        "status": state.get("status", "unknown"),
        "retry_count": state.get("retry_count", 0),
        "referenced_tables": state.get("referenced_tables", []),
        "row_count": result.get("row_count", 0),
        "truncated": result.get("truncated", False),
        "guardrail_status": state.get("guardrail_status", "not_run"),
    }


def sanitize_error(error: Exception | str) -> str:
    """Keep the UI error useful without echoing credentials or connection strings."""
    text = str(error)
    for marker in ("key=", "api_key=", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        if marker.lower() in text.lower():
            return f"The request failed ({type(error).__name__ if isinstance(error, Exception) else 'Error'}). Check API credentials, model availability, network access, or provider quota."
    return text[:500]
