"""SQL and prompt safety checks for read-only analytics."""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # Allows lightweight local tests before dependencies are installed.
    sqlglot = None
    exp = None

from app.config import ALLOWED_TABLES, MAX_RESULT_ROWS


class SQLSafetyError(ValueError):
    """Raised when a generated statement is not safe for read-only execution."""


@dataclass(frozen=True)
class SQLValidationResult:
    sql: str
    tables: tuple[str, ...]
    row_limit_added: bool


BLOCKED_REQUEST_PATTERNS = (
    re.compile(r"\b(drop|delete|truncate|alter|update|insert|create table|attach database)\b", re.I),
    re.compile(r"\b(readfile|writefile|load_extension)\s*\(", re.I),
    re.compile(r"<\s*script\b", re.I),
)

BLOCKED_AST_TYPES = (
    (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Transaction)
    if exp is not None else ()
)

BLOCKED_FUNCTIONS = {"READFILE", "WRITEFILE", "LOAD_EXTENSION", "EDIT"}


def validate_user_question(question: str) -> None:
    """Reject obvious requests to mutate data before any LLM call is made."""
    if not question or not question.strip():
        raise SQLSafetyError("Please enter an analytics question.")
    if len(question) > 2_000:
        raise SQLSafetyError("The question is too long. Please keep it under 2,000 characters.")
    for pattern in BLOCKED_REQUEST_PATTERNS:
        if pattern.search(question):
            raise SQLSafetyError(
                "This application is read-only. Requests to modify, delete, or create database data are not allowed."
            )


def validate_readonly_sql(sql: str, *, max_rows: int = MAX_RESULT_ROWS) -> SQLValidationResult:
    """Parse SQL, allow one SELECT/WITH query, enforce table allowlist and row cap."""
    if not sql or not sql.strip():
        raise SQLSafetyError("The SQL generator returned an empty query.")
    if len(sql) > 20_000:
        raise SQLSafetyError("Generated SQL is too long.")

    if sqlglot is None:
        return _fallback_validate_readonly_sql(sql, max_rows=max_rows)

    try:
        statements = [statement for statement in sqlglot.parse(sql, read="sqlite") if statement is not None]
    except sqlglot.errors.ParseError as exc:
        details = exc.errors[0].get("description", "invalid syntax") if exc.errors else "invalid syntax"
        raise SQLSafetyError(f"SQL could not be parsed: {details}") from exc

    if len(statements) != 1:
        raise SQLSafetyError("Only one SQL statement is allowed.")

    expression = statements[0]
    if not isinstance(expression, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLSafetyError("Only read-only SELECT queries are allowed.")

    for blocked_type in BLOCKED_AST_TYPES:
        if expression.find(blocked_type) is not None:
            raise SQLSafetyError(f"Blocked SQL operation: {blocked_type.__name__}.")

    if expression.find(exp.Into) is not None:
        raise SQLSafetyError("SELECT INTO is not allowed.")

    for function in expression.find_all(exp.Func):
        function_name = function.sql_name().upper()
        if isinstance(function, exp.Anonymous):
            function_name = str(function.this).upper()
        if function_name in BLOCKED_FUNCTIONS:
            raise SQLSafetyError(f"The SQL function {function_name} is not allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
    referenced_tables: list[str] = []
    for table in expression.find_all(exp.Table):
        table_name = table.name.lower()
        if table_name in cte_names:
            continue
        if table_name not in ALLOWED_TABLES:
            raise SQLSafetyError(f"Table '{table.name}' is not available. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}.")
        referenced_tables.append(table_name)

    if not referenced_tables:
        raise SQLSafetyError("The query must read from an approved database table.")

    row_limit_added = False
    current_limit = expression.args.get("limit")
    if current_limit is None:
        expression = expression.limit(max_rows)
        row_limit_added = True
    else:
        limit_value = current_limit.expression
        if not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
            raise SQLSafetyError("LIMIT must be a positive integer literal.")
        requested_limit = int(limit_value.this)
        if requested_limit < 1:
            raise SQLSafetyError("LIMIT must be greater than zero.")
        if requested_limit > max_rows:
            expression = expression.limit(max_rows)
            row_limit_added = True

    return SQLValidationResult(
        sql=expression.sql(dialect="sqlite"),
        tables=tuple(sorted(set(referenced_tables))),
        row_limit_added=row_limit_added,
    )


def _fallback_validate_readonly_sql(sql: str, *, max_rows: int) -> SQLValidationResult:
    """Conservative fallback validator used only when SQLGlot is unavailable.

    Normal installations use SQLGlot's parsed AST. This scanner intentionally
    accepts a narrower subset of SQL and should not replace SQLGlot in production.
    """
    # Remove comments and string literals before checking dangerous tokens.
    cleaned = re.sub(r"/\*.*?\*/|--[^\r\n]*", " ", sql, flags=re.DOTALL)
    without_strings = re.sub(r"'(?:''|[^'])*'", "''", cleaned)
    stripped = without_strings.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].rstrip()
    if ";" in stripped:
        raise SQLSafetyError("Only one SQL statement is allowed.")
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise SQLSafetyError("Only read-only SELECT queries are allowed.")

    blocked = re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|PRAGMA|ATTACH|DETACH|VACUUM|REINDEX|ANALYZE|INTO)\b",
        without_strings,
        re.IGNORECASE,
    )
    if blocked:
        raise SQLSafetyError(f"Blocked SQL operation: {blocked.group(1).upper()}.")

    function_match = re.search(r"\b(READFILE|WRITEFILE|LOAD_EXTENSION)\s*\(", without_strings, re.IGNORECASE)
    if function_match:
        raise SQLSafetyError(f"The SQL function {function_match.group(1).upper()} is not allowed.")

    cte_names = {name.lower() for name in re.findall(r"(?:WITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", stripped, re.IGNORECASE)}
    table_matches = re.findall(
        r"\b(?:FROM|JOIN)\s+([\w]+|\"[\w]+\"|`[\w]+`|\[[\w]+\])",
        stripped,
        re.IGNORECASE,
    )
    referenced_tables = []
    for raw_name in table_matches:
        table_name = raw_name.strip('"`[]').lower()
        if table_name in cte_names:
            continue
        if table_name not in ALLOWED_TABLES:
            raise SQLSafetyError(f"Table '{table_name}' is not available. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}.")
        referenced_tables.append(table_name)

    if not referenced_tables:
        raise SQLSafetyError("The query must read from an approved database table.")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\s*$", stripped, re.IGNORECASE)
    row_limit_added = False
    if limit_match:
        requested = int(limit_match.group(1))
        if requested < 1:
            raise SQLSafetyError("LIMIT must be greater than zero.")
        if requested > max_rows:
            stripped = stripped[:limit_match.start(1)] + str(max_rows)
            row_limit_added = True
    else:
        stripped = f"{stripped} LIMIT {max_rows}"
        row_limit_added = True

    return SQLValidationResult(
        sql=stripped,
        tables=tuple(sorted(set(referenced_tables))),
        row_limit_added=row_limit_added,
    )
