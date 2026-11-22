
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from app.config import GOOGLE_API_KEY, GOOGLE_MODEL
from app.data_import import import_dataframe, normalize_identifier
from app.dashboard import (
    build_result_frame,
    chart_suggestion,
    execution_telemetry,
    sanitize_error,
)
from app.database import (
    create_readonly_engine,
    get_table_counts,
    reflect_schema,
)
from app.graph import run_query
from app.llm_provider import gemini_configuration_status
from database.seed import seed_database


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="SQL Database Analytics Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def initialize_database():
    try:
        engine = create_readonly_engine()
        engine.dispose()
    except FileNotFoundError:
        seed_database()


def load_workspace():
    try:
        schema = reflect_schema()
        counts = get_table_counts()
        return schema, counts
    except FileNotFoundError:
        return {}, {}


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------

def render_sidebar():

    with st.sidebar:

        st.title("📊 Data Analyst")
        st.caption("SQL & Database Analytics Agent")

        st.divider()

        page = st.radio(
            "Navigation",
            [
                "Ask Data",
                "Add Data",
                "Schema Explorer",
                "About",
            ],
        )

        st.divider()

        st.subheader("AI Model")

        model_status = gemini_configuration_status()

        if model_status.get("configured"):
            st.success(
                f"Connected: {model_status.get('model', GOOGLE_MODEL)}"
            )
        else:
            st.error("Gemini API key not configured")

        st.divider()

        st.subheader("Database")

        try:
            counts = get_table_counts()

            st.metric("Tables", len(counts))
            st.metric(
                "Total Records",
                f"{sum(counts.values()):,}"
            )

        except Exception:
            st.warning("Database unavailable")

        st.divider()

        st.caption("SQL execution is read-only.")

    return page


# --------------------------------------------------
# CHAT: RUN USER QUESTION
# --------------------------------------------------

def run_user_question(question):

    question = question.strip()

    if not question:
        return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    if not GOOGLE_API_KEY:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "Gemini API key is missing. Check your .env file.",
                "state": None,
            }
        )

        return

    try:

        with st.spinner("Analyzing your question..."):

            result = run_query(question)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "Here are the results.",
                "state": result,
            }
        )

    except Exception as error:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": sanitize_error(error),
                "state": None,
            }
        )


# --------------------------------------------------
# DISPLAY QUERY RESULTS
# --------------------------------------------------

def display_query_result(state, download_key):

    status = state.get("status")

    if status == "blocked":

        st.warning(
            state.get(
                "error_message",
                "This request was blocked by security checks."
            )
        )

        return

    if status != "success":

        st.error("Unable to complete the query.")

        if state.get("error_message"):
            st.caption(sanitize_error(state["error_message"]))

        return

    result = state.get("db_result") or {}

    frame = build_result_frame(result)

    # RESULT METRICS

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Rows returned",
        result.get("row_count", len(result.get("rows", [])))
    )

    col2.metric(
        "Tables used",
        len(state.get("referenced_tables", []))
    )

    col3.metric(
        "SQL corrections",
        state.get("retry_count", 0)
    )

    # RESULT TABS

    result_tab, chart_tab, sql_tab, trace_tab = st.tabs(
        [
            "Results",
            "Charts",
            "Generated SQL",
            "Execution Details",
        ]
    )

    with result_tab:

        if not frame.empty:

            st.dataframe(
                frame,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                label="Download CSV",
                data=frame.to_csv(index=False).encode("utf-8"),
                file_name="analytics_results.csv",
                mime="text/csv",
                key=f"download_csv_{download_key}",
            )

            if result.get("truncated"):
                st.info("Results were limited by the configured row limit.")

        else:

            st.info("The query returned no matching records.")

    with chart_tab:

        figure = chart_suggestion(frame)

        if figure is not None:
            st.plotly_chart(
                figure,
                use_container_width=True,
            )
        else:
            st.info(
                "No suitable chart was identified for this result."
            )

    with sql_tab:

        st.caption("Validated SQL executed against the database.")

        st.code(
            state.get("validated_sql")
            or state.get("generated_sql")
            or "No SQL generated.",
            language="sql",
        )

    with trace_tab:

        st.subheader("Execution Telemetry")

        st.json(execution_telemetry(state))

        st.subheader("Execution History")

        for item in state.get("execution_history", []):
            st.write("•", item)

        history = state.get("self_correction_history", [])

        if history:

            with st.expander("SQL correction history"):

                for item in history:
                    st.write("•", item)


# --------------------------------------------------
# PAGE 1: ASK DATA
# --------------------------------------------------

def ask_data_page(schema, counts):

    st.title("Ask Data")

    st.write(
        "Ask questions about your database in natural language. "
        "The AI agent generates SQL, validates it and displays the results."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Available Tables", len(schema))

    col2.metric(
        "Total Records",
        f"{sum(counts.values()):,}"
    )

    col3.metric(
        "AI Model",
        GOOGLE_MODEL if GOOGLE_API_KEY else "Not connected"
    )

    st.divider()

    if not schema:

        st.warning("No data available. Upload a dataset to get started.")

        if st.button("Go to Add Data"):
            st.session_state["navigation"] = "Add Data"
            st.rerun()

        return

    st.subheader("Suggested Questions")

    table_names = list(schema.keys())

    suggestions = [
        f"Show the first 10 records from {table_names[0]}",
        "Which category generates the highest revenue?",
        "Show the total number of records in each table.",
        "Compare monthly sales performance.",
    ]

    columns = st.columns(2)

    for index, suggestion in enumerate(suggestions):

        with columns[index % 2]:

            if st.button(
                suggestion,
                use_container_width=True,
                key=f"suggestion_{index}",
            ):

                run_user_question(suggestion)
                st.rerun()

    st.divider()

    st.subheader("Conversation")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message_index, message in enumerate(st.session_state.messages):

        with st.chat_message(message["role"]):

            st.write(message["content"])

        if message["role"] == "assistant":

            state = message.get("state")

            if state:
                display_query_result(
                    state,
                    download_key=message_index,
                )

    question = st.chat_input(
        "Ask something about your data..."
    )

    if question:

        run_user_question(question)
        st.rerun()


# --------------------------------------------------
# READ CSV AND EXCEL FILES
# --------------------------------------------------

def read_uploaded_file(uploaded_file, selected_sheet=None):

    content = uploaded_file.getvalue()

    extension = Path(uploaded_file.name).suffix.lower()

    if extension == ".csv":

        return pd.read_csv(io.BytesIO(content))

    if extension == ".xlsx":

        return pd.read_excel(
            io.BytesIO(content),
            sheet_name=selected_sheet or 0,
            engine="openpyxl",
        )

    raise ValueError("Only CSV and XLSX files are supported.")


# --------------------------------------------------
# PAGE 2: ADD DATA
# --------------------------------------------------

def add_data_page(schema, counts):

    st.title("Add Data")

    st.write(
        "Upload your own CSV or Excel dataset. "
        "The application will store it as a new SQLite table "
        "that the AI agent can query."
    )

    st.divider()

    st.subheader("Upload Dataset")

    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"],
    )

    if uploaded_file is not None:

        if uploaded_file.size > 25 * 1024 * 1024:

            st.error("File size exceeds the 25 MB limit.")
            return

        selected_sheet = None

        try:

            if uploaded_file.name.lower().endswith(".xlsx"):

                workbook = pd.ExcelFile(
                    io.BytesIO(uploaded_file.getvalue()),
                    engine="openpyxl",
                )

                selected_sheet = st.selectbox(
                    "Select Excel worksheet",
                    workbook.sheet_names,
                )

            dataframe = read_uploaded_file(
                uploaded_file,
                selected_sheet,
            )

        except Exception as error:

            st.error(f"Unable to read file: {sanitize_error(error)}")
            return

        if dataframe.empty:

            st.warning("The uploaded dataset is empty.")
            return

        st.subheader("Dataset Preview")

        st.write(
            f"Rows: {len(dataframe):,} | "
            f"Columns: {len(dataframe.columns):,}"
        )

        st.dataframe(
            dataframe.head(10),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        st.subheader("Import Settings")

        default_name = Path(uploaded_file.name).stem

        table_name_input = st.text_input(
            "Enter table name",
            value=default_name,
        )

        try:

            table_name = normalize_identifier(
                table_name_input,
                fallback="uploaded_data",
            )

        except ValueError as error:

            st.error(str(error))
            return

        if table_name in schema:

            st.error(
                f"The table '{table_name}' already exists. "
                "Choose a different name."
            )

        else:

            if st.button(
                "Import Dataset",
                type="primary",
            ):

                try:

                    imported = import_dataframe(
                        dataframe,
                        table_name,
                    )

                    st.success(
                        f"Successfully imported "
                        f"{imported['rows_imported']:,} rows "
                        f"into table '{imported['table_name']}'."
                    )

                    st.rerun()

                except Exception as error:

                    st.error(sanitize_error(error))

    st.divider()

    st.subheader("Existing Database Tables")

    if counts:

        table_data = []

        for table_name, row_count in counts.items():

            table_data.append(
                {
                    "Table Name": table_name,
                    "Records": row_count,
                    "Columns": len(
                        schema.get(table_name, {}).get("columns", [])
                    ),
                    "Source": (
                        "Sample Data"
                        if table_name in {"customers", "orders", "sales"}
                        else "Uploaded Data"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(table_data),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info("No database tables available.")


# --------------------------------------------------
# PAGE 3: SCHEMA EXPLORER
# --------------------------------------------------

def schema_explorer_page(schema, counts):

    st.title("Schema Explorer")

    st.write(
        "Explore the structure of your database, "
        "including tables, columns, primary keys and foreign keys."
    )

    st.divider()

    if not schema:

        st.info("No database tables found.")
        return

    st.subheader("Database Overview")

    overview = []

    for table_name, details in schema.items():

        overview.append(
            {
                "Table": table_name,
                "Records": counts.get(table_name, 0),
                "Columns": len(details.get("columns", [])),
                "Foreign Keys": len(details.get("foreign_keys", [])),
            }
        )

    st.dataframe(
        pd.DataFrame(overview),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Table Details")

    for table_name, details in schema.items():

        with st.expander(
            f"{table_name} ({counts.get(table_name, 0):,} records)"
        ):

            columns_data = []

            for column in details.get("columns", []):

                columns_data.append(
                    {
                        "Column Name": column["name"],
                        "Data Type": str(column["type"]),
                        "Nullable": column.get("nullable", True),
                        "Primary Key": column.get("primary_key", False),
                    }
                )

            st.write("Columns")

            st.dataframe(
                pd.DataFrame(columns_data),
                use_container_width=True,
                hide_index=True,
            )

            foreign_keys = details.get("foreign_keys", [])

            st.write("Foreign Key Relationships")

            if foreign_keys:

                relationships = []

                for fk in foreign_keys:

                    for source, target in zip(
                        fk.get("constrained_columns", []),
                        fk.get("referred_columns", []),
                    ):

                        relationships.append(
                            {
                                "Foreign Key": source,
                                "Referenced Table": fk.get("referred_table"),
                                "Referenced Column": target,
                            }
                        )

                st.dataframe(
                    pd.DataFrame(relationships),
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.caption("No foreign keys declared for this table.")


# --------------------------------------------------
# PAGE 4: ABOUT
# --------------------------------------------------

def about_page():

    st.title("About the Application")

    st.write(
        "SQL & Database Analytics Agent is an AI-powered "
        "application that allows users to analyze structured "
        "data using natural-language questions."
    )

    st.divider()

    st.subheader("How It Works")

    st.markdown(
        """
        1. **User Input:** The user asks a business question.
        2. **Schema Inspection:** SQLAlchemy retrieves database metadata.
        3. **SQL Generation:** Gemini generates an SQL query.
        4. **SQL Validation:** SQLGlot checks query safety.
        5. **Query Execution:** SQLite executes the validated query.
        6. **Result Analysis:** Pandas processes the returned data.
        7. **Visualization:** Plotly displays suitable charts.
        """
    )

    st.divider()

    st.subheader("Technology Stack")

    st.markdown(
        """
        - Python
        - Streamlit
        - Google Gemini
        - LangGraph
        - SQLAlchemy
        - SQLite
        - SQLGlot
        - Pandas
        - Plotly
        """
    )

    st.divider()

    st.subheader("Supported Data Formats")

    st.write("CSV (.csv) and Excel (.xlsx)")


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

def main():

    try:

        initialize_database()

    except Exception as error:

        st.error(
            f"Database initialization failed: {sanitize_error(error)}"
        )

        st.stop()

    page = render_sidebar()

    schema, counts = load_workspace()

    if page == "Ask Data":

        ask_data_page(schema, counts)

    elif page == "Add Data":

        add_data_page(schema, counts)

    elif page == "Schema Explorer":

        schema_explorer_page(schema, counts)

    elif page == "About":

        about_page()


if __name__ == "__main__":
    main()