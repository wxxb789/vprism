from __future__ import annotations

from datetime import UTC, datetime

import duckdb

from vprism.core.data import schema
from vprism.core.data.ingestion import IngestionConfig, RawRecord, ingest


def _make_record(symbol: str, ts: datetime) -> RawRecord:
    return RawRecord(
        supplier_symbol=symbol,
        timestamp=ts,
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=100.0,
        provider="akshare",
    )


def test_duplicates_are_dropped_when_not_allowed() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    ts = datetime(2024, 1, 1, tzinfo=UTC)
    records = [_make_record("000001", ts), _make_record("000001", ts)]

    config = IngestionConfig(allow_duplicates=False)
    result = ingest(conn, records, provider="akshare", market="CN", config=config)

    assert result.written_rows == 1
    assert result.duplicates_dropped == 1
    assert any(summary.code == "DUPLICATE_ROW" for summary in result.fail_reasons)

    rows = conn.execute("SELECT COUNT(*) FROM raw_ohlcv").fetchone()[0]
    assert rows == 1


def test_duplicates_inserted_when_allowed() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    ts = datetime(2024, 1, 1, tzinfo=UTC)
    records = [_make_record("000001", ts), _make_record("000001", ts)]

    config = IngestionConfig(allow_duplicates=True)
    result = ingest(conn, records, provider="akshare", market="CN", config=config)

    assert result.written_rows == 1
    assert result.duplicates_dropped == 1
    assert result.rejected_rows == 0
    assert any(summary.code == "DUPLICATE_ROW" for summary in result.fail_reasons)

    rows = conn.execute("SELECT COUNT(*) FROM raw_ohlcv").fetchone()[0]
    assert rows == 1
