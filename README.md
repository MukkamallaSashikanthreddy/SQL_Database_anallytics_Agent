# SQL & Database Analytics Agent

A Streamlit application for exploring relational data through natural-language questions. Users can upload CSV or Excel datasets, store them as tables in a local SQLite database, ask questions in plain English, and inspect the generated SQL, query results, and visualizations.

The application uses Google Gemini to generate SQL, LangGraph to coordinate the workflow, SQLGlot to validate generated queries, SQLAlchemy to inspect and access the database, and Pandas and Plotly to present the results.

## Features

### Ask Data

- Ask questions about the tables in the active SQLite database using natural language.
- Generate SQLite queries with Google Gemini.
- Display query results in a table.
- Suggest and render Plotly charts when the result contains suitable dimensions and measures.
- View the validated SQL statement and execution details.
- Download query results as CSV.
- Review earlier questions and results during the active Streamlit session.

### Add Data

- Upload CSV (`.csv`) and Excel (`.xlsx`) files.
- Select a worksheet when an Excel workbook contains multiple sheets.
- Preview the uploaded dataset before importing it.
- Choose a table name for the imported dataset.
- Add the dataset as a new table in the SQLite database.
- Keep existing tables intact; an import is rejected when the requested table name already exists.

Import constraints:

- Maximum uploaded file size in the interface: 25 MB.
- Maximum dataset size: 100,000 rows and 100 columns.
- Table and column names are normalized to lowercase identifiers containing letters, numbers, and underscores.
- Duplicate column names after normalization and nested cell values are rejected.
- CSV and Excel imports create tables from the tabular data. Primary keys and foreign-key constraints are not automatically inferred from uploaded files.

### Schema Explorer

- List all user-created tables in the SQLite database.
- Show row counts and column counts.
- Inspect column names, data types, nullability, and primary-key information.
- Display declared foreign-key relationships in readable tables.
- Include imported tables in the schema reflected for subsequent questions.

### Query safety and execution visibility

- Apply deterministic input checks before schema inspection and model invocation.
- Optionally run a NeMo Guardrails input self-check.
- Reflect the active database schema before generating SQL.
- Parse and validate generated SQL with SQLGlot.
- Permit one read-only query and reject write operations, multiple statements, external schema references, and selected dangerous SQLite functions.
- Revalidate SQL immediately before execution.
- Execute agent-generated queries through a SQLite read-only connection.
- Enforce a maximum query result size of 1,000 rows by default.
- Allow a bounded number of SQL correction attempts when validation or execution fails.
- Display generated SQL, execution status, referenced tables, retry count, and execution history.

## Application workflow

```text
User question
     |
     v
Streamlit interface
     |
     v
Input validation and guardrails
     |
     v
SQLAlchemy schema reflection
     |
     v
Gemini SQL generation
     |
     v
SQLGlot validation
     |
     v
Read-only SQLite execution
     |
     +------ Query error ------> Bounded SQL correction
     |                               |
     |<------------------------------+
     v
Pandas result processing
     |
     v
Streamlit table, Plotly chart, SQL and execution details
```

The LangGraph workflow carries the user question, reflected schema, generated SQL, validated SQL, database result, error details, retry count, status, and execution history between its nodes.

## Technology stack

| Technology | Purpose |
|---|---|
| Python 3.11 | Application runtime |
| Streamlit | User interface |
| Google Gemini | Natural-language-to-SQL generation |
| LangGraph | Agent workflow orchestration |
| LangChain Core | Model message and integration abstractions |
| `langchain-google-genai` | Gemini integration |
| SQLAlchemy 2.x | SQLite access and schema reflection |
| SQLGlot | SQL parsing and AST-based validation |
| SQLite | Local relational database |
| Pandas | Dataset import and result processing |
| openpyxl | Excel workbook reading |
| Plotly | Interactive charts |
| NeMo Guardrails | Optional input self-check |
| pytest | Automated tests |
| python-dotenv | Environment variable loading |

The standard SQL-generation path uses Gemini. NeMo live inference is disabled by default; when enabled, it uses the separately configured OpenAI model in `config/guardrails/config.yml` and requires an OpenAI API key.

## Project structure

```text
SQL-Database-Analytics-Agent/
├── .env                         # Local API keys and settings (not committed)
├── .env.example                 # Environment variable template
├── .gitignore                   # Ignore rules for secrets and generated files
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── app.py                       # Streamlit application entry point
├── setup_windows.bat            # Windows environment setup
├── run_windows.bat              # Windows application launcher
├── seed_database.bat            # Sample database seeder launcher
├── app/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py                 # Application configuration
│   ├── dashboard.py              # Result dataframe, chart and telemetry helpers
│   ├── data_import.py             # CSV/Excel validation and SQLite import
│   ├── database.py               # SQLite access, schema reflection and query execution
│   ├── gemini_diagnostic.py       # Gemini connectivity diagnostic
│   ├── graph.py                  # LangGraph workflow and state
│   ├── guardrails.py             # Deterministic and optional NeMo input guardrails
│   ├── llm_provider.py            # Gemini model configuration and factory
│   ├── security.py                # SQLGlot-based SQL validation
│   └── streamlit_app.py           # Streamlit pages and interface
├── config/
│   └── guardrails/
│       ├── config.yml             # NeMo model and rail configuration
│       ├── prompts.yml            # NeMo input self-check prompt
│       └── rails.co               # Guardrail response text
├── database/
│   ├── __init__.py
│   └── seed.py                    # Sample database schema and data
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_agent.py
    ├── test_dashboard.py
    ├── test_data_import.py
    ├── test_gemini_diagnostic.py
    ├── test_guardrails.py
    ├── test_guardrails_nemo.py
    ├── test_llm_provider.py
    ├── test_security.py
    └── test_seed.py
```

## Requirements

- Windows 10/11 or another operating system that supports Python 3.11 and the listed dependencies.
- Python 3.11.
- Internet access for dependency installation and Gemini API requests.
- A Google AI Studio API key for SQL generation.
- An OpenAI API key only when optional NeMo live inference is enabled.

## Setup on Windows

Run commands from the project root directory (the folder containing `app.py` and `requirements.txt`).

### 1. Create a virtual environment

```powershell
py -3.11 -m venv .venv
```

### 2. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Alternatively, run the included setup script:

```powershell
.\setup_windows.bat
```

The setup script creates the virtual environment, installs dependencies, copies `.env.example` to `.env` if `.env` does not exist, and seeds the sample database if the database file is missing.

### 3. Configure environment variables

Create `.env` from the template if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Open `.env`:

```powershell
notepad .env
```

Set the required Gemini key and confirm the model identifier is available to your Google AI Studio project:

```env
GOOGLE_API_KEY=your_google_ai_studio_api_key
GOOGLE_MODEL=gemini-3.5-flash-lite
DATABASE_URL=sqlite:///database/analytics.db
NEMO_GUARDRAILS_CONFIG=config/guardrails
NEMO_LIVE_INFERENCE=false
OPENAI_API_KEY=
MAX_SQL_RETRIES=3
MAX_RESULT_ROWS=1000
```

`GOOGLE_MODEL` can be changed to another Gemini model available to your API key. Do not place real API keys in source files or commit `.env` to Git. Commit `.env.example` with placeholder values only.

## Sample database

The sample database is stored at `database/analytics.db` and is created by `database/seed.py`.

It contains three related tables:

| Table | Description | Sample rows |
|---|---|---:|
| `customers` | Customer name, city, region, and segment | 6 |
| `orders` | Order identifier, customer, date, and status | 10 |
| `sales` | Products, categories, quantities, prices, costs, and discounts for each order line | 20 |

The sample schema declares these relationships:

- `orders.customer_id` references `customers.customer_id`.
- `sales.order_id` references `orders.order_id`.

To create or recreate the sample tables, run:

```powershell
.\.venv\Scripts\python.exe -m database.seed
```

**Important:** The seeder drops and recreates the sample `customers`, `orders`, and `sales` tables. Back up any changes to those sample tables before running it. Uploaded tables with other names are not part of the sample seed schema.

## Run the application

Use the included launcher:

```powershell
.\run_windows.bat
```

Or run Streamlit directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed in the terminal. Streamlit normally uses `http://localhost:8501`.

## Using the application

1. Open **Add Data** to upload a `.csv` or `.xlsx` file. Preview the data, select an Excel worksheet if needed, and enter a table name.
2. Import the dataset. It is saved as a new table in the configured SQLite database. Existing table names cannot be overwritten through the import interface.
3. Open **Schema Explorer** to inspect the available tables, columns, data types, row counts, primary keys, and declared foreign-key relationships.
4. Open **Ask Data** and ask a question about the available data. The agent reflects the current schema and uses it as context for SQL generation.
5. Review the result table, suggested visualization, validated SQL, and execution details. Export tabular results using the CSV download control when needed.

Example questions for the sample database:

- How many orders are present in the database?
- Which product categories generated the most revenue?
- Who are the top five customers by order value?
- Show monthly sales revenue.
- Compare sales across regions.
- How many orders are there for each status?
- Calculate gross profit by product category.

Questions for uploaded datasets should refer to the actual table and column names shown in Schema Explorer.

## Gemini connectivity check

To check Gemini connectivity separately from the Streamlit interface, run:

```powershell
.\.venv\Scripts\python.exe -m app.gemini_diagnostic
```

The diagnostic reports the configured model and whether the request succeeds. It does not print the API key.

## Optional NeMo Guardrails input self-check

Deterministic input checks always run. NeMo live inference is optional and disabled by default.

To enable it:

1. Set `NEMO_LIVE_INFERENCE=true` in `.env`.
2. Set `OPENAI_API_KEY` to a valid key for the OpenAI model configured in `config/guardrails/config.yml` (`gpt-4o-mini` in the supplied configuration).
3. Restart the application.

The optional NeMo input check uses a separate provider from Gemini and may incur separate API charges. It is not required for normal SQL generation. If NeMo is enabled but cannot verify the request, the application blocks that request.

## Run tests

Install the project dependencies, then run the complete test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For verbose output:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

The tests cover the LangGraph workflow, read-only SQL execution, SQL validation, input guardrails, Gemini configuration and diagnostics, dataset import, database seeding, result processing, and chart selection. Model and guardrail calls are mocked in tests; passing the test suite does not replace a live Gemini connectivity check.

## Configuration reference

| Variable | Purpose | Default |
|---|---|---|
| `GOOGLE_API_KEY` | Google Gemini API key | Not set |
| `GOOGLE_MODEL` | Gemini model identifier | `gemini-3.5-flash-lite` |
| `DATABASE_URL` | SQLite database location | `sqlite:///database/analytics.db` |
| `MAX_SQL_RETRIES` | Maximum SQL correction retries | `3` |
| `MAX_RESULT_ROWS` | Maximum rows returned by an agent query | `1000` |
| `NEMO_LIVE_INFERENCE` | Enable optional NeMo input inference | `false` |
| `NEMO_GUARDRAILS_CONFIG` | NeMo configuration directory | `config/guardrails` |
| `OPENAI_API_KEY` | Key for optional NeMo inference | Not set |

## Data handling and security notes

- The SQLite database is stored locally at the path configured by `DATABASE_URL`.
- Imported CSV/Excel data is written to SQLite using a dedicated import connection. Agent-generated queries use a separate read-only SQLite connection.
- Imported tables are not automatically assigned primary keys or foreign-key constraints. The Schema Explorer displays relationships that are actually declared in the database.
- Generated SQL is validated before execution and restricted to tables reflected from the active database schema.
- The agent accepts read-only queries; data-changing SQL is not executed by the agent.
- Query results are capped by `MAX_RESULT_ROWS` (maximum supported setting: 1,000 rows in this configuration).
- Input and SQL validation reduce common unsafe requests and query patterns but do not guarantee protection against every possible model error or attack.
- The application does not provide user authentication, role-based access control, multi-user isolation, or production-grade audit management. Use appropriate access controls before exposing it to other users or connecting sensitive datasets.
- Keep `.env`, API keys, and local database files out of source control. The included `.gitignore` excludes these local files.

## Known limitations

- SQLite is the configured database backend; other database engines are not currently supported by this application configuration.
- CSV and `.xlsx` are the supported upload formats. Legacy `.xls`, JSON, and database backup files are not accepted by the upload page.
- Uploaded datasets are imported as new tables. Existing tables are not updated or merged by the upload workflow.
- Relationships between uploaded tables are not automatically inferred. Add declared keys/relationships separately when joined analysis requires them.
- Query generation depends on Gemini API availability, API key permissions, network access, and the model configured for the Google project.
- Natural-language interpretation and generated SQL should be reviewed using the displayed SQL and result data, especially for financial or operational decisions.
