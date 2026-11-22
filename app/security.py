"""SQLGlot AST validation for one read-only SQLite query."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp

from app.config import ALLOWED_TABLES, MAX_RESULT_ROWS


class SQLValidationError(ValueError):
    """Raised when generated SQL does not satisfy the read-only policy."""


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    tables: tuple[str, ...]
    limit_added_or_clamped: bool


BLOCKED_EXPRESSIONS = tuple(
    expression for expression in (
        getattr(exp, "Insert", None), getattr(exp, "Update", None),
        getattr(exp, "Delete", None), getattr(exp, "Create", None),
        getattr(exp, "Drop", None), getattr(exp, "Alter", None),
        getattr(exp, "Command", None), getattr(exp, "Transaction", None),
        getattr(exp, "Grant", None), getattr(exp, "Revoke", None),
    ) if expression is not None
)

BLOCKED_FUNCTION_NAMES = {
    "READFILE", "WRITEFILE", "LOAD_EXTENSION", "EDIT", "CSV",
    "WRITEFILE", "READFILE",
}


def validate_sql(
    sql: str,
    *,
    max_rows: int = MAX_RESULT_ROWS,
    allowed_tables: set[str] | None = None,
) -> ValidatedSQL:
    if not sql or not sql.strip():
        raise SQLValidationError("The model returned an empty SQL query.")
    if len(sql) > 30_000:
        raise SQLValidationError("Generated SQL exceeds the maximum allowed length.")
    if max_rows < 1:
        raise ValueError("max_rows must be positive.")

    try:
        statements = [statement for statement in sqlglot.parse(sql, read="sqlite") if statement is not None]
    except sqlglot.errors.ParseError as exc:
        detail = exc.errors[0].get("description", "invalid syntax") if exc.errors else "invalid syntax"
        raise SQLValidationError(f"SQL parsing failed: {detail}.") from exc

    if len(statements) != 1:
        raise SQLValidationError("Only one SQL statement is permitted.")

    tree = statements[0]
    allowed_query_types = tuple(
        cls for cls in (getattr(exp, "Select", None), getattr(exp, "Union", None),
                        getattr(exp, "Intersect", None), getattr(exp, "Except", None))
        if cls is not None
    )
    if not isinstance(tree, allowed_query_types):
        raise SQLValidationError("Only read-only SELECT queries are allowed.")

    for blocked_type in BLOCKED_EXPRESSIONS:
        if tree.find(blocked_type) is not None:
            raise SQLValidationError(f"Blocked SQL operation: {blocked_type.__name__}.")

    # Locking clauses and SELECT INTO are not valid for this read-only analytics app.
    lock_type = getattr(exp, "Lock", None)
    if lock_type is not None and tree.find(lock_type) is not None:
        raise SQLValidationError("Locking clauses are not allowed.")
    into_type = getattr(exp, "Into", None)
    if into_type is not None and tree.find(into_type) is not None:
        raise SQLValidationError("SELECT INTO is not allowed.")

    for function in tree.find_all(exp.Func):
        function_name = function.sql_name().upper()
        if isinstance(function, getattr(exp, "Anonymous", ())):
            function_name = str(function.this).upper()
        if function_name in BLOCKED_FUNCTION_NAMES:
            raise SQLValidationError(f"The SQLite function {function_name} is not allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    approved_tables = {name.lower() for name in (allowed_tables if allowed_tables is not None else ALLOWED_TABLES)}
    referenced_tables: set[str] = set()
    for table in tree.find_all(exp.Table):
        table_name = table.name.lower()
        if table_name in cte_names:
            continue
        if table_name not in approved_tables:
            allowed_text = ", ".join(sorted(approved_tables)) or "(none)"
            raise SQLValidationError(
                f"Table '{table.name}' is not available. Allowed tables: {allowed_text}."
            )
        referenced_tables.add(table_name)

    if not referenced_tables:
        raise SQLValidationError("The query must read from one of the available data tables.")

    # Reject table-valued pragma/virtual-table constructs and unsupported schema references.
    for table in tree.find_all(exp.Table):
        if table.db or table.catalog:
            raise SQLValidationError("Qualified external database or schema references are not allowed.")

    limit_added = False
    limit_node = tree.args.get("limit")
    if limit_node is None:
        tree = tree.limit(max_rows)
        limit_added = True
    else:
        limit_expression = limit_node.expression
        if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
            raise SQLValidationError("LIMIT must be a positive integer literal.")
        requested = int(limit_expression.this)
        if requested < 1:
            raise SQLValidationError("LIMIT must be greater than zero.")
        if requested > max_rows:
            tree = tree.limit(max_rows)
            limit_added = True

    return ValidatedSQL(
        sql=tree.sql(dialect="sqlite"),
        tables=tuple(sorted(referenced_tables)),
        limit_added_or_clamped=limit_added,
    )
