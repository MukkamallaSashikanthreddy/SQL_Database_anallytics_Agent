# Architecture notes

## Request lifecycle

1. Streamlit collects the natural-language question.
2. `validate_user_question` blocks obvious mutation instructions and invalid input before a model call.
3. LangGraph loads the database schema.
4. SQL generation uses Gemini or the limited no-key demo planner.
5. SQLGlot parses the query and verifies it is a single read-only query over allowlisted tables.
6. The validator appends or clamps `LIMIT` to the configured maximum.
7. The SQLite executor connects using `mode=ro` and `PRAGMA query_only=ON`.
8. If execution fails, the graph can retry within a configured attempt budget. The new SQL is validated again.
9. The result is explained and converted to a Pandas DataFrame; a Plotly chart is suggested when the result shape supports one.

## State carried by LangGraph

`AgentState` carries the question, schema, generated and validated SQL, referenced tables, result columns and rows, errors, retry count, execution mode, and a human-readable event history.

## Trust boundaries

- The LLM is untrusted: its SQL must pass deterministic validation.
- The executor is read-only: it opens a read-only SQLite URI and enables query-only mode.
- The database schema passed to the LLM is introspection output, not an instruction.
- Model output is displayed as text; it is not executed as Python.
- The demo planner only maps several common example question patterns to prewritten SQL. It is not described as general language understanding.

## Known limitations

- The starter dataset is synthetic.
- Demo mode recognizes a limited set of question patterns.
- Gemini mode requires a working API key, supported model and network access.
- SQL validators reduce risk but do not eliminate all semantic errors. Incorrect joins or business definitions can still produce syntactically valid but misleading analytics.
- The sample app has no authentication or role-based access control and should not be connected to sensitive production databases.
