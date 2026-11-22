from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect, text

from app.data_import import import_dataframe, normalize_identifier, prepare_dataframe
from app.database import create_readonly_engine, reflect_schema


def test_normalize_identifier_converts_spaces_and_punctuation():
    assert normalize_identifier("Monthly Sales 2026!") == "monthly_sales_2026"


def test_normalize_identifier_prefixes_numeric_name():
    assert normalize_identifier("2026_sales") == "table_2026_sales"


def test_normalize_identifier_rejects_sqlite_internal_prefix():
    with pytest.raises(ValueError, match="reserved"):
        normalize_identifier("sqlite_sequence")


def test_prepare_dataframe_normalizes_columns():
    frame = prepare_dataframe(pd.DataFrame({"Customer Name": ["Asha"], "Order-Value": [125.0]}))
    assert list(frame.columns) == ["customer_name", "order_value"]


def test_prepare_dataframe_rejects_duplicate_normalized_columns():
    frame = pd.DataFrame([[1, 2]], columns=["Customer ID", "customer-id"])
    with pytest.raises(ValueError, match="identical"):
        prepare_dataframe(frame)


def test_prepare_dataframe_rejects_empty_dataframe():
    with pytest.raises(ValueError, match="no data rows"):
        prepare_dataframe(pd.DataFrame(columns=["name"]))


def test_import_dataframe_creates_table_and_reflects_it(tmp_path):
    db_path = tmp_path / "custom.db"
    frame = pd.DataFrame({"Region Name": ["South", "North"], "Net Revenue": [120.5, 98.0]})

    result = import_dataframe(frame, "regional revenue", db_path=db_path)

    assert result["table_name"] == "regional_revenue"
    assert result["rows_imported"] == 2
    assert result["columns_imported"] == 2

    engine = create_readonly_engine(db_path)
    try:
        schema = reflect_schema(engine)
        assert "regional_revenue" in schema
        assert [column["name"] for column in schema["regional_revenue"]["columns"]] == ["region_name", "net_revenue"]
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT * FROM regional_revenue ORDER BY region_name")).all()
        assert len(rows) == 2
    finally:
        engine.dispose()


def test_import_dataframe_never_overwrites_existing_table(tmp_path):
    db_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE metrics (value INTEGER)"))
            connection.execute(text("INSERT INTO metrics(value) VALUES (7)"))
    finally:
        engine.dispose()

    with pytest.raises(ValueError, match="never overwritten"):
        import_dataframe(pd.DataFrame({"value": [99]}), "metrics", db_path=db_path)

    verify_engine = create_readonly_engine(db_path)
    try:
        with verify_engine.connect() as connection:
            assert connection.execute(text("SELECT value FROM metrics")).scalar_one() == 7
    finally:
        verify_engine.dispose()
