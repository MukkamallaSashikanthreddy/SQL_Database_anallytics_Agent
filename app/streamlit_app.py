"""Single-page Streamlit interface for the SQL & Database Analytics Agent."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics import choose_chart, format_currency, result_dataframe
from app.config import DATABASE_PATH, GEMINI_API_KEY
from app.database import connect_readonly, get_dashboard_metrics
from app.graph import run_agent
from app.security import SQLSafetyError
from database.seed import seed_database


st.set_page_config(
    page_title="SQL Analytics Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def ensure_database() -> None:
    if not Path(DATABASE_PATH).exists():
        seed_database(DATABASE_PATH)


def fetch_dataframe(sql: str, params: tuple = ()) -> pd.DataFrame:
    connection = connect_readonly(DATABASE_PATH)
    try:
        return pd.read_sql_query(sql, connection, params=params)
    finally:
        connection.close()


def render_overview() -> None:
    metrics = get_dashboard_metrics()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net sales revenue", format_currency(metrics["revenue"]))
    col2.metric("Orders", f"{metrics['order_count']:,}")
    col3.metric("Customers", f"{metrics['customer_count']:,}")
    margin = (metrics["gross_profit"] / metrics["revenue"] * 100) if metrics["revenue"] else 0
    col4.metric("Gross margin", f"{margin:.1f}%")

    monthly = fetch_dataframe(
        """
        SELECT strftime('%Y-%m', o.order_date) AS month,
               SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)) AS revenue
        FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.status != 'Cancelled'
        GROUP BY month ORDER BY month
        """
    )
    region = fetch_dataframe(
        """
        SELECT c.region,
               SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)) AS revenue
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.status != 'Cancelled'
        GROUP BY c.region ORDER BY revenue DESC
        """
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Monthly revenue trend")
        if not monthly.empty:
            fig = px.line(monthly, x="month", y="revenue", markers=True)
            fig.update_layout(template="plotly_white", yaxis_title="Revenue (₹)", xaxis_title="Month")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Revenue by region")
        if not region.empty:
            fig = px.bar(region, x="region", y="revenue")
            fig.update_layout(template="plotly_white", yaxis_title="Revenue (₹)", xaxis_title="Region")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top-selling products")
    top_products = fetch_dataframe(
        """
        SELECT p.product_name, p.category,
               SUM(oi.quantity) AS units_sold,
               ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
        FROM products p JOIN order_items oi ON oi.product_id = p.product_id
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status != 'Cancelled'
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY revenue DESC LIMIT 8
        """
    )
    st.dataframe(top_products, use_container_width=True, hide_index=True)


def render_agent() -> None:
    st.subheader("Ask your database")
    st.write("Ask business questions in plain English. The agent generates SQL, validates it, runs it in read-only mode, and explains the result.")

    mode = st.radio(
        "Agent mode",
        ["Demo mode (no API key)", "Gemini mode (API key required)"],
        horizontal=True,
        help="Demo mode uses a small set of deterministic example queries. Gemini mode handles broader natural-language questions.",
    )
    use_gemini = mode.startswith("Gemini")
    if use_gemini and not GEMINI_API_KEY:
        st.warning("GEMINI_API_KEY is not configured. Add it to your .env file, then restart Streamlit.")

    examples = [
        "Which product categories generated the most revenue?",
        "Show monthly sales revenue.",
        "Who are the top five customers by order value?",
        "How many orders were placed in each status?",
        "Compare revenue across regions.",
    ]
    selected_example = st.selectbox("Try an example", ["Choose an example..."] + examples)
    with st.form("question_form", clear_on_submit=False):
        question = st.text_area(
            "Your question",
            value="" if selected_example == "Choose an example..." else selected_example,
            height=90,
            placeholder="e.g. Which product category generated the highest revenue?",
        )
        submitted = st.form_submit_button("Analyze", type="primary", use_container_width=True)

    if submitted:
        if use_gemini and not GEMINI_API_KEY:
            st.error("Gemini mode needs a GEMINI_API_KEY. Use Demo mode or configure your key in .env.")
            return
        if not question.strip():
            st.warning("Enter a question first.")
            return
        try:
            with st.spinner("Analyzing your question and querying the database..."):
                result = run_agent(question, use_gemini=use_gemini)
            st.session_state["last_agent_result"] = result
            st.session_state["last_question"] = question
        except SQLSafetyError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"The analysis could not be completed: {type(exc).__name__}: {exc}")
            return

    result = st.session_state.get("last_agent_result")
    if result:
        st.divider()
        st.markdown("#### Agent response")
        if result.get("status") == "completed":
            st.success(result.get("explanation", "Analysis completed."))
        else:
            st.error(result.get("explanation", "The analysis failed."))
            if result.get("error"):
                st.caption(result["error"])

        rows = result.get("rows", [])
        if rows:
            data = result_dataframe(rows)
            st.markdown("#### Query results")
            st.dataframe(data, use_container_width=True, hide_index=True)
            chart, chart_note = choose_chart(data)
            if chart is not None:
                st.markdown("#### Suggested visualization")
                st.plotly_chart(chart, use_container_width=True)
                st.caption(chart_note)
            csv = data.to_csv(index=False).encode("utf-8")
            st.download_button("Download results as CSV", csv, "query_results.csv", "text/csv")

        with st.expander("Generated SQL"):
            st.code(result.get("validated_sql") or result.get("sql", "No SQL generated."), language="sql")
        with st.expander("Agent execution trace"):
            for event in result.get("history", []):
                st.write(f"• {event}")
            st.caption(f"Mode: {result.get('mode', 'unknown')} · Attempts: {result.get('attempts', 0)} · Tables: {', '.join(result.get('tables', []))}")


def render_data_explorer() -> None:
    st.subheader("Database explorer")
    table = st.selectbox("Select a table", ["customers", "products", "orders", "order_items"])
    connection = connect_readonly(DATABASE_PATH)
    try:
        data = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT 500', connection)
    finally:
        connection.close()
    st.caption(f"Showing up to 500 rows from `{table}`.")
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        f"Download {table}.csv",
        data.to_csv(index=False).encode("utf-8"),
        f"{table}.csv",
        "text/csv",
    )


def main() -> None:
    ensure_database()
    with st.sidebar:
        st.title("📊 SQL Analytics Agent")
        st.caption("Natural-language business intelligence")
        page = st.radio("Navigation", ["Overview", "Ask the Agent", "Data Explorer", "About"])
        st.divider()
        st.caption("Database")
        st.code(str(DATABASE_PATH), language="text")
        st.caption("Security: generated SQL is validated and executed read-only.")

    st.title("SQL & Database Analytics Agent")
    st.caption("Turn natural-language questions into safe, explainable SQL analytics.")

    if page == "Overview":
        render_overview()
    elif page == "Ask the Agent":
        render_agent()
    elif page == "Data Explorer":
        render_data_explorer()
    else:
        st.markdown(
            """
            ### What this application demonstrates
            - Natural-language-to-SQL analytics with a LangGraph workflow.
            - Gemini integration for SQL generation and result interpretation.
            - SQLGlot validation before execution.
            - SQLite read-only query execution and bounded result sizes.
            - Streamlit dashboard, Pandas result tables and Plotly charts.
            - A deterministic demo mode for exploring the application without an API key.

            ### Important limitation
            Demo mode is a small set of example intents, not a general-purpose language model. Use Gemini mode for open-ended questions. Always verify important business decisions against the underlying data.
            """
        )


if __name__ == "__main__":
    main()
