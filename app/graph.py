"""LangGraph StateGraph for safe natural-language-to-SQL analytics."""
from __future__ import annotations

import re
from typing import Any, TypedDict, Callable

from app.config import LANGGRAPH_RECURSION_LIMIT, MAX_SQL_RETRIES
from app.database import create_readonly_engine, execute_readonly_sql, format_schema, reflect_schema
from app.guardrails import InputBlockedError, check_user_input
from app.llm_provider import get_gemini_model, response_text
from app.security import SQLValidationError, validate_sql


SQL_GENERATION_PROMPT = """You are a careful SQLite analytics engineer. Convert the user's business question into exactly ONE SQLite SELECT query.

Rules:
- Return SQL only. Do not use Markdown fences or add an explanation.
- Use only tables and columns explicitly present in the reflected schema below.
- Treat this as an arbitrary user dataset: do not assume e-commerce, customers, orders, sales, or any fixed column names.
- Only SELECT statements or read-only WITH ... SELECT queries are permitted.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, ATTACH, DETACH, VACUUM, or SELECT INTO.
- Do not query SQLite internal tables or invent table/column names.
- Use reflected foreign-key relationships when a JOIN is needed. Do not guess relationships that are not shown.
- Use appropriate aggregate functions and GROUP BY for summaries.
- For date/time analysis, use the date formats and columns shown in the schema.
- Add LIMIT 1000 or less for row-returning queries.

REFLECTED DATABASE SCHEMA:
{schema}

USER QUESTION:
{user_query}

PREVIOUS QUERY ERROR (empty on first attempt):
{error_message}

CORRECTION ATTEMPT: {retry_count}
"""


class AgentState(TypedDict, total=False):
    user_query: str
    normalized_query: str
    schema: dict[str, Any]
    schema_text: str
    generated_sql: str
    validated_sql: str
    db_result: dict[str, Any]
    error_message: str
    retry_count: int
    status: str
    execution_history: list[str]
    self_correction_history: list[str]
    referenced_tables: list[str]
    guardrail_status: str


def extract_sql(content: str) -> str:
    value = content.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", value, re.I | re.S)
    if fenced:
        value = fenced.group(1).strip()
    value = re.sub(r"^SQL\s*:\s*", "", value, flags=re.I)
    return value.strip()


def _history(state: AgentState, message: str) -> list[str]:
    return list(state.get("execution_history", [])) + [message]


def _guard_input(state: AgentState) -> dict[str, Any]:
    try:
        normalized = check_user_input(state.get("user_query", ""))
        return {
            "normalized_query": normalized,
            "guardrail_status": "passed",
            "status": "input_accepted",
            "error_message": "",
            "execution_history": _history(state, "Input passed deterministic safety checks"),
        }
    except InputBlockedError as exc:
        return {
            "guardrail_status": "blocked",
            "status": "blocked",
            "error_message": str(exc),
            "execution_history": _history(state, "Input blocked before schema inspection or Gemini invocation"),
        }


def _inspect_schema(state: AgentState, engine_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    engine = engine_factory() if engine_factory is not None else create_readonly_engine()
    try:
        schema = reflect_schema(engine)
        if not schema:
            raise RuntimeError("No data tables were found. Add a CSV/Excel dataset from the Data workspace or load the sample database.")
        return {
            "schema": schema,
            "schema_text": format_schema(schema),
            "status": "schema_loaded",
            "error_message": "",
            "execution_history": _history(state, f"Reflected schema for {len(schema)} available tables"),
        }
    finally:
        engine.dispose()


def _generate_sql(state: AgentState, model: Any) -> dict[str, Any]:
    prompt = SQL_GENERATION_PROMPT.format(
        schema=state.get("schema_text", ""),
        user_query=state.get("normalized_query", state.get("user_query", "")),
        error_message=state.get("error_message", ""),
        retry_count=state.get("retry_count", 0),
    )
    response = model.invoke(prompt)
    generated = extract_sql(response_text(response))
    return {
        "generated_sql": generated,
        "status": "sql_generated",
        "error_message": "",
        "execution_history": _history(state, f"Gemini generated SQL (attempt {state.get('retry_count', 0) + 1})"),
    }


def _validate_generated_sql(state: AgentState) -> dict[str, Any]:
    try:
        validated = validate_sql(
            state.get("generated_sql", ""),
            allowed_tables=set(state.get("schema", {}).keys()),
        )
        return {
            "validated_sql": validated.sql,
            "referenced_tables": list(validated.tables),
            "status": "sql_validated",
            "error_message": "",
            "execution_history": _history(state, f"SQLGlot accepted read-only SQL for: {', '.join(validated.tables)}"),
        }
    except SQLValidationError as exc:
        return {
            "status": "sql_validation_error",
            "error_message": str(exc),
            "retry_count": state.get("retry_count", 0) + 1,
            "self_correction_history": list(state.get("self_correction_history", [])) + [f"Validation rejected SQL: {exc}"],
            "execution_history": _history(state, "Generated SQL rejected by SQLGlot before database execution"),
        }


def _execute_query(state: AgentState, engine_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    try:
        # The SQL is validated again immediately before execution.
        final_validation = validate_sql(
            state.get("validated_sql", ""),
            allowed_tables=set(state.get("schema", {}).keys()),
        )
        engine = engine_factory() if engine_factory is not None else create_readonly_engine()
        try:
            result = execute_readonly_sql(final_validation.sql, engine=engine)
        finally:
            engine.dispose()
        return {
            "validated_sql": final_validation.sql,
            "db_result": result,
            "status": "success",
            "error_message": "",
            "execution_history": _history(state, f"Read-only query executed; {result['row_count']} row(s) returned"),
        }
    except Exception as exc:
        # Avoid surfacing secrets/connection URLs in the correction prompt or UI.
        safe_error = f"{type(exc).__name__}: {str(exc)[:1200]}"
        return {
            "status": "execution_error",
            "error_message": safe_error,
            "retry_count": state.get("retry_count", 0) + 1,
            "self_correction_history": list(state.get("self_correction_history", [])) + [f"Database rejected query: {safe_error}"],
            "execution_history": _history(state, "Database execution failed; error sent to the SQL correction step"),
        }


def _should_continue(state: AgentState) -> str:
    if state.get("status") in {"success", "blocked"}:
        return "finish"
    if int(state.get("retry_count", 0)) <= MAX_SQL_RETRIES:
        return "retry"
    return "failed"


def _mark_failed(state: AgentState) -> dict[str, Any]:
    return {
        "status": "failed",
        "execution_history": _history(state, "Stopped after the configured SQL correction retry limit"),
    }


def build_graph(model: Any | None = None, engine_factory: Callable[[], Any] | None = None):
    """Create the LangGraph workflow. Dependencies can be injected for deterministic tests."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("LangGraph is not installed. Run `pip install -r requirements.txt`.") from exc

    active_model = model or get_gemini_model()
    builder = StateGraph(AgentState)
    builder.add_node("guard_input", _guard_input)
    builder.add_node("inspect_schema", lambda state: _inspect_schema(state, engine_factory))
    builder.add_node("generate_sql", lambda state: _generate_sql(state, active_model))
    builder.add_node("validate_sql", _validate_generated_sql)
    builder.add_node("execute_query", lambda state: _execute_query(state, engine_factory))
    builder.add_node("mark_failed", _mark_failed)

    builder.add_edge(START, "guard_input")
    builder.add_conditional_edges(
        "guard_input",
        lambda state: "blocked" if state.get("status") == "blocked" else "continue",
        {"blocked": END, "continue": "inspect_schema"},
    )
    builder.add_edge("inspect_schema", "generate_sql")
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_conditional_edges(
        "validate_sql",
        lambda state: "execute" if state.get("status") == "sql_validated" else _should_continue(state),
        {"execute": "execute_query", "retry": "generate_sql", "failed": "mark_failed", "finish": END},
    )
    builder.add_conditional_edges(
        "execute_query",
        lambda state: _should_continue(state),
        {"finish": END, "retry": "generate_sql", "failed": "mark_failed"},
    )
    builder.add_edge("mark_failed", END)
    return builder.compile()


def run_query(
    user_query: str,
    *,
    model: Any | None = None,
    engine_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    graph = build_graph(model=model, engine_factory=engine_factory)
    return graph.invoke(
        {
            "user_query": user_query,
            "retry_count": 0,
            "execution_history": [],
            "self_correction_history": [],
            "status": "started",
        },
        {"recursion_limit": LANGGRAPH_RECURSION_LIMIT},
    )
