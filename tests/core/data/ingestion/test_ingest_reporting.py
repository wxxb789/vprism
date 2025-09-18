from __future__ import annotations

from datetime import UTC, datetime

import duckdb

from vprism.core.data import schema
from vprism.core.data.ingestion import RawRecord, ingest


def _record(symbol: str, **overrides: object) -> RawRecord:
    record = RawRecord(
        supplier_symbol=symbol,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=100.0,
        provider="akshare",
    )
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


def test_fail_reasons_group_multiple_codes() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    records = [
        _record("000001"),
        _record("000002", open=None),
        _record("000003", volume=None),
        _record("000004", low=12.0),
    ]

    result = ingest(conn, records, provider="akshare", market="CN")

    fail_counts = {summary.code: summary.count for summary in result.fail_reasons}

    assert fail_counts["MISSING_FIELD"] >= 1
    assert fail_counts["MISSING_VOLUME_DEFAULTED"] == 1
    assert fail_counts["LOW_ABOVE_HIGH"] == 1
    assert result.rejected_rows == 2
    assert result.written_rows == 2

    rows = conn.execute("SELECT supplier_symbol FROM raw_ohlcv ORDER BY supplier_symbol").fetchall()
    assert [row[0] for row in rows] == ["000001", "000003"]
