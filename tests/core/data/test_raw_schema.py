from __future__ import annotations

import duckdb

from datetime import datetime

from vprism.core.data import schema
from vprism.core.data.ingestion.models import RawRecord


def test_raw_ohlcv_table_has_expected_columns_and_constraints() -> None:
    conn = duckdb.connect(database=":memory:")

    schema.RAW_OHLCV_TABLE.ensure(conn)

    column_info = conn.execute("PRAGMA table_info('raw_ohlcv')").fetchall()
    column_names = [row[1] for row in column_info]
    not_null_columns = {row[1] for row in column_info if row[3] == 1}
    primary_key_columns = {row[1] for row in column_info if row[5] > 0}

    assert column_names == [
        "supplier_symbol",
        "market",
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "provider",
        "batch_id",
        "ingest_time",
    ]
    assert not_null_columns == {
        "supplier_symbol",
        "market",
        "ts",
        "provider",
        "batch_id",
        "ingest_time",
    }
    assert primary_key_columns == {
        "supplier_symbol",
        "market",
        "ts",
        "batch_id",
    }


def test_raw_ohlcv_table_create_ddl_includes_primary_key() -> None:
    ddl = schema.RAW_OHLCV_TABLE.create_ddl()

    assert "CREATE TABLE IF NOT EXISTS raw_ohlcv" in ddl
    assert "PRIMARY KEY (supplier_symbol, market, ts, batch_id)" in ddl


def test_raw_record_defaults_allow_missing_optional_fields() -> None:
    record = RawRecord(
        supplier_symbol="000001",
        timestamp=datetime(2024, 1, 1, 0, 0, 0),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
    )

    assert record.volume is None
    assert record.provider is None
