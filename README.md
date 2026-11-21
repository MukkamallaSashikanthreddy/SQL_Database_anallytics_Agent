# SQL & Database Analytics Agent

A Streamlit-only natural-language analytics application. Ask questions about a sample commerce database in plain English; the agent generates SQL, validates it, executes it using a read-only SQLite connection, and displays the results with suggested Plotly visualizations.

> This is an independently written portfolio implementation inspired by the general idea of natural-language database analytics. It is not a copy of another repository. Add your own improvements and understand the code before presenting it as your work.

## Features

- **Streamlit-only UI:** dashboard, chat-style analytics workflow, data explorer, CSV downloads.
- **Agent workflow:** LangGraph graph with schema loading, SQL generation, validation, execution, bounded correction attempts, and result explanation.
- **Gemini integration:** optional `langchain-google-genai` provider for open-ended natural-language-to-SQL generation and explanation.
- **No-key demo mode:** a small deterministic planner demonstrates the application with several supported example questions. This is a demo fallback, not a general-purpose LLM.
- **SQL safety:** SQLGlot AST validation permits read-only queries over the four sample tables, blocks DDL/DML and dangerous functions, and adds or clamps a result limit.
- **Read-only database access:** SQLite connections use `mode=ro` and `PRAGMA query_only=ON` for analytics queries.
- **Analytics:** seeded customers, products, orders and order items; KPI overview; monthly revenue; regional revenue; top products.
- **Testing:** tests cover database seeding, schema discovery, read-only enforcement, SQL validation, chart selection and demo-agent execution.

## Architecture

```text
                 Streamlit UI (app.py)
                         |
             +-----------+------------+
             |                        |
        Overview / Explorer      Ask the Agent
                                      |
                                  LangGraph
                                      |
                   +------------------+-------------------+
                   |                  |                   |
               Load Schema       Generate SQL        Explain Result
                                      |
                                SQLGlot Validation
                                      |
                              Read-only SQLite Query
                                      |
                           Pandas Results + Plotly Chart
```

All UI and orchestration run in the same Streamlit Python process. There is no FastAPI service or React frontend.

## Project structure

```text
SQL-Database-Analytics-Agent/
├── app.py                    # Streamlit entry point
├── app/
│   ├── analytics.py          # Result tables and chart suggestions
│   ├── config.py             # Environment and application settings
│   ├── database.py           # Read-only SQLite helpers
│   ├── demo_planner.py       # Limited no-key example question planner
│   ├── graph.py              # LangGraph SQL analytics workflow
│   ├── llm.py                # Optional Gemini model factory
│   ├── security.py           # Prompt and SQL safety checks
│   └── streamlit_app.py      # Streamlit pages and interaction
├── database/
│   └── seed.py               # Reproducible local sample data
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_analytics.py
│   ├── test_seed_and_database.py
│   └── test_security.py
├── scripts/
│   └── smoke_test.py         # No-API data-to-chart smoke test
├── eval/
│   └── eval_set.json         # Example question/expected-column cases
├── .env.example
├── .gitignore
├── requirements.txt
├── setup_windows.bat
└── run_windows.bat
```

## Requirements

- Python 3.11 (recommended)
- Windows 10/11, macOS or Linux
- Gemini API key only if you want open-ended Gemini mode

The application can be explored in Demo mode without an API key.

## Windows setup

1. Extract the project ZIP.
2. Open the extracted `SQL-Database-Analytics-Agent` folder in VS Code.
3. Double-click `setup_windows.bat`, or run the commands below in PowerShell.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m database.seed
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

To use Gemini, open `.env` and set:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
```

Never commit `.env` or API keys to GitHub.

## Run the application

```powershell
streamlit run app.py
```

Or double-click `run_windows.bat` after setup.

Streamlit will print a local URL, normally `http://localhost:8501`.

## Try these example questions

The no-key Demo mode supports a limited set of examples:

- Which product categories generated the most revenue?
- Show monthly sales revenue.
- Who are the top five customers by order value?
- How many orders were placed in each status?
- Compare revenue across regions.
- Which products generated the highest sales?

Gemini mode can handle a wider range of questions based on the actual schema. Results should still be checked before business decisions are made.

## Database tables

| Table | Description |
|---|---|
| `customers` | Customer name, city, region and segment |
| `products` | Product category, selling price and unit cost |
| `orders` | Customer, order date, status and payment method |
| `order_items` | Product, quantity, item price and discount |

Revenue is calculated as `quantity * unit_price * (1 - discount_pct)`. Cancelled orders are excluded from standard revenue and order-performance queries.

The generated database is intentionally excluded from Git. Re-create it at any time with:

```powershell
python -m database.seed
```

To delete and rebuild the generated sample database, use `python -m database.seed --reset`. Only use `--reset` with the local sample database; it deletes the specified database file before re-seeding.

## Run tests

```powershell
python -m pytest -q
```

Run a no-API end-to-end smoke test of seeding → planning → validation → read-only execution → chart selection:

```powershell
python scripts/smoke_test.py
```

To see each test name:

```powershell
python -m pytest -v
```

Tests use temporary local databases and do not require a Gemini API key. The LangGraph integration tests require the project dependencies to be installed. The tests do not prove that a live Gemini service, account quota, or external network connection will always be available.

## SQL safety design

1. The user's natural-language request is checked for obvious data-modification requests.
2. The LLM is instructed to generate one read-only SELECT query using the supplied schema.
3. SQLGlot parses the generated query. Only read-only query structures referencing allowlisted tables are accepted.
4. Dangerous statements and selected SQLite file/extension functions are rejected.
5. A maximum result limit is added or enforced.
6. The query executes against a SQLite connection opened in read-only mode with `PRAGMA query_only=ON`.
7. On a database error, LangGraph may request a corrected query, but every attempt goes through the same validator and row limit. Retries are bounded.

The application is designed for a local portfolio demonstration, not as a production multi-tenant analytics service. For production, add user authentication, authorization at the database level, query auditing, stronger prompt-injection defenses, resource isolation, and human review of sensitive analytics.

## Evaluation notes

The repository includes `eval/eval_set.json` as a starter set of representative questions and expected output columns. Before describing model accuracy on a resume, run a repeatable evaluation against a documented dataset and report the measured results. Do not claim an accuracy percentage based only on a few example questions.

## GitHub publishing

Create an empty GitHub repository (do not initialize another README if you keep this local README). From the extracted project folder:

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Initial commit: SQL Database Analytics Agent"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If Git reports that `origin` already exists, update it instead:

```powershell
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
```

If you want all commits to be from today's work, start from this clean project folder and initialize a new Git repository. Do not copy the old `.git` directory from the reference project. The commit date will be the actual date and time when you run `git commit`.

## Suggested resume description (after you personally run and verify it)

**SQL & Database Analytics Agent | Python, Streamlit, LangGraph, Gemini, SQLite, SQLGlot, Pandas, Plotly**

- Built a Streamlit analytics assistant that translates natural-language business questions into SQL queries over a relational commerce database.
- Orchestrated schema retrieval, SQL generation, validation, read-only execution and bounded query repair using LangGraph.
- Added SQLGlot validation, table allowlisting, result limits and SQLite read-only connections to reduce unsafe query execution.
- Presented query outputs using Pandas tables and automatically suggested Plotly visualizations.

Only list Gemini mode, LangGraph execution and test counts after you have run them successfully in your own environment.

## Credits and licence

This is a fresh implementation created for learning and portfolio use. Keep this README's provenance statement and add your own meaningful features and documentation as you develop it. No third-party source code is bundled intentionally. Review the licence terms of dependencies you install.
