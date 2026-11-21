"""LangGraph workflow for safe natural-language SQL analytics."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import DATABASE_PATH, MAX_SQL_ATTEMPTS
from app.database import execute_readonly_query, get_database_schema
from app.llm import get_gemini_model, invoke_text
from app.demo_planner import demo_sql
from app.security import SQLSafetyError, validate_readonly_sql, validate_user_question


class AgentState(TypedDict, total=False):
    question: str
    schema: str
    sql: str
    validated_sql: str
    tables: list[str]
    columns: list[str]
    rows: list[dict[str, Any]]
    error: str
    attempts: int
    status: str
    explanation: str
    history: list[str]
    mode: str
    db_path: str


SQL_SYSTEM_PROMPT = """You are a careful SQLite analytics engineer. Convert the business question into exactly one read-only SQL query.

Rules:
- Return SQL only, without Markdown fences or explanations.
- Only SELECT or WITH ... SELECT statements are permitted.
- Use only the tables and columns in the provided schema.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, ATTACH, DETACH, or SELECT INTO.
- Never query sqlite_master or internal SQLite tables.
- Use explicit joins and avoid duplicate counting.
- Revenue is SUM(order_items.quantity * order_items.unit_price * (1 - order_items.discount_pct)).
- Gross profit is revenue minus SUM(order_items.quantity * products.unit_cost).
- Exclude cancelled orders from revenue and order performance unless the user explicitly asks about cancellations.
- Use date filters against ISO-formatted YYYY-MM-DD order_date values.
- Include a reasonable LIMIT (at most 1000).

Database schema:
{schema}

Business question:
{question}

Previous attempt feedback (if any):
{feedback}
"""

EXPLANATION_PROMPT = """Explain the result of this SQL analytics query for a business user.
Be precise, do not invent numbers, and only describe patterns supported by the result.
If the result is empty, say no matching records were found.

Question: {question}
SQL: {sql}
Columns: {columns}
Rows (up to 20): {rows}
"""


def _extract_sql(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    # Remove a leading SQL label sometimes emitted by models.
    text = re.sub(r"^SQL\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _generate_sql(state: AgentState, model: Any | None) -> dict[str, Any]:
    attempts = int(state.get("attempts", 0)) + 1
    if model is None:
        sql = demo_sql(state["question"])
        mode = "demo"
    else:
        feedback = state.get("error", "None")
        prompt = SQL_SYSTEM_PROMPT.format(
            schema=state.get("schema", ""),
            question=state["question"],
            feedback=feedback,
        )
        sql = _extract_sql(invoke_text(model, prompt))
        mode = "gemini"
    history = list(state.get("history", []))
    history.append(f"Attempt {attempts}: SQL generated ({mode} mode).")
    return {"sql": sql, "attempts": attempts, "mode": mode, "error": "", "history": history}


def _validate_sql(state: AgentState) -> dict[str, Any]:
    try:
        validation = validate_readonly_sql(state["sql"])
        return {
            "validated_sql": validation.sql,
            "tables": list(validation.tables),
            "error": "",
            "status": "validated",
            "history": list(state.get("history", [])) + ["SQL passed read-only validation."],
        }
    except SQLSafetyError as exc:
        return {
            "error": str(exc),
            "status": "validation_error",
            "history": list(state.get("history", [])) + [f"SQL validation blocked the query: {exc}"],
        }


def _execute_sql(state: AgentState) -> dict[str, Any]:
    try:
        columns, rows = execute_readonly_query(state["validated_sql"], state.get("db_path", str(DATABASE_PATH)))
        return {
            "columns": columns,
            "rows": rows,
            "error": "",
            "status": "success",
            "history": list(state.get("history", [])) + [f"Query executed successfully; {len(rows)} row(s) returned."],
        }
    except Exception as exc:  # Error text is fed back to the model for bounded correction.
        return {
            "error": f"Database execution error: {type(exc).__name__}: {exc}",
            "status": "execution_error",
            "history": list(state.get("history", [])) + [f"Query execution failed: {type(exc).__name__}."],
        }


def _explain(state: AgentState, model: Any | None) -> dict[str, Any]:
    rows = state.get("rows", [])
    if not rows:
        explanation = "The query completed successfully, but no matching records were found."
    elif model is not None:
        prompt = EXPLANATION_PROMPT.format(
            question=state["question"],
            sql=state.get("validated_sql", ""),
            columns=state.get("columns", []),
            rows=rows[:20],
        )
        explanation = invoke_text(model, prompt)
    else:
        explanation = f"The query returned {len(rows)} row(s) across {len(state.get('columns', []))} column(s). Review the result table and chart for the detailed breakdown."
    return {
        "explanation": explanation,
        "status": "completed",
        "history": list(state.get("history", [])) + ["Result explanation generated."],
    }


def _retry_or_finish(state: AgentState) -> str:
    if int(state.get("attempts", 0)) < MAX_SQL_ATTEMPTS:
        return "retry"
    return "finish"


def _finish_error(state: AgentState) -> dict[str, Any]:
    return {
        "status": "failed",
        "explanation": "I could not produce a safe, executable query within the retry limit. Please rephrase the question or check the database schema.",
        "history": list(state.get("history", [])) + ["Stopped after reaching the retry limit."],
    }


def build_agent_graph(*, model: Any | None = None):
    """Build and compile the LangGraph workflow. Pass model=None for local demo mode."""
    graph = StateGraph(AgentState)

    def load_schema_node(state: AgentState) -> dict[str, Any]:
        schema = get_database_schema(state.get("db_path", str(DATABASE_PATH)))
        return {"schema": schema, "history": list(state.get("history", [])) + ["Database schema loaded."]}

    def generate_node(state: AgentState) -> dict[str, Any]:
        return _generate_sql(state, model)

    def explain_node(state: AgentState) -> dict[str, Any]:
        return _explain(state, model)

    graph.add_node("load_schema", load_schema_node)
    graph.add_node("generate_sql", generate_node)
    graph.add_node("validate_sql", _validate_sql)
    graph.add_node("execute_sql", _execute_sql)
    graph.add_node("explain", explain_node)
    graph.add_node("finish_error", _finish_error)

    graph.add_edge(START, "load_schema")
    graph.add_edge("load_schema", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges(
        "validate_sql",
        lambda state: "execute" if state.get("status") == "validated" else _retry_or_finish(state),
        {"execute": "execute_sql", "retry": "generate_sql", "finish": "finish_error"},
    )
    graph.add_conditional_edges(
        "execute_sql",
        lambda state: "explain" if state.get("status") == "success" else _retry_or_finish(state),
        {"explain": "explain", "retry": "generate_sql", "finish": "finish_error"},
    )
    graph.add_edge("explain", END)
    graph.add_edge("finish_error", END)
    return graph.compile()


def run_agent(
    question: str,
    *,
    db_path: str = str(DATABASE_PATH),
    model: Any | None = None,
    use_gemini: bool = False,
) -> dict[str, Any]:
    """Run the agent in demo or Gemini mode and return the final graph state."""
    validate_user_question(question)
    if use_gemini and model is None:
        model = get_gemini_model()
    graph = build_agent_graph(model=model)
    return graph.invoke({
        "question": question,
        "db_path": db_path,
        "attempts": 0,
        "history": [],
        "mode": "gemini" if model is not None else "demo",
    })
