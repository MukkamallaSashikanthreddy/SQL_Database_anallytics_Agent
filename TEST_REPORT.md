# Local build verification report

Verification date: 2026-11-21

## Results

- Python bytecode compilation: passed (`python -m compileall -q app database tests scripts app.py`).
- Automated tests: **28 passed, 1 skipped**.
- Data-to-chart smoke test: passed (`python scripts/smoke_test.py`).
- Smoke path covered: seed a temporary SQLite database → discover schema → select demo SQL → validate SQL → execute through a read-only connection → create a Pandas result frame → select a Plotly chart.

## Skipped / not verified in this build environment

- LangGraph integration tests were skipped because LangGraph was not installed in the build environment and package-index network access was unavailable. The project includes LangGraph as a dependency and the full `StateGraph` implementation; run `python -m pytest -q` after installing `requirements.txt` on your machine to exercise those tests.
- The SQLGlot AST-validator path was not exercised here because SQLGlot could not be installed in this environment. The security tests exercised the conservative fallback validator. Normal project installation includes SQLGlot, and the application uses its AST validator when installed.
- A live Gemini API call was not run. Gemini mode requires your own API key, network access and an available model quota. Demo mode works without a key.
- Streamlit UI was compile-checked but not launched in this environment because Streamlit could not be installed here.

These limitations are intentionally recorded so the repository does not claim unverified live integration results.
