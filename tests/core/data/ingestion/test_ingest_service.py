from __future__ import annotations

from datetime import UTC, datetime

import duckdb
import pytest

from vprism.core.data import schema
from vprism.core.data.ingestion import (
    IngestionConfig,
    IngestionConfigError,
    IngestionResult,
    RawRecord,
    ingest,
)


def _make_record(**overrides: object) -> RawRecord:
    base = RawRecord(
        supplier_symbol="000001",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=100.0,
        provider=None,
    )
    for field, value in overrides.items():
        setattr(base, field, value)
    return base


def test_ingest_persists_valid_rows_and_defaults_missing_volume() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    records = [
        _make_record(volume=None),
        _make_record(supplier_symbol="000002", volume=200.0),
    ]

    result = ingest(conn, records, provider="akshare", market="CN")

    assert isinstance(result, IngestionResult)
    assert result.written_rows == 2
    assert result.rejected_rows == 0
    assert result.duplicates_dropped == 0

    rows = conn.execute("SELECT supplier_symbol, volume, provider, batch_id, ingest_time FROM raw_ohlcv ORDER BY supplier_symbol").fetchall()
    assert [row[0] for row in rows] == ["000001", "000002"]
    assert rows[0][1] == -1.0
    assert rows[0][2] == "akshare"
    assert rows[0][3] == result.batch_id
    assert rows[0][4] is not None
    assert rows[1][1] == 200.0
    assert any(summary.code == "MISSING_VOLUME_DEFAULTED" for summary in result.fail_reasons)


def test_invalid_rows_are_rejected_and_not_persisted() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    valid = _make_record()
    invalid = _make_record(open=12.0)

    result = ingest(conn, [valid, invalid], provider="akshare", market="CN")

    assert result.written_rows == 1
    assert result.rejected_rows == 1
    assert any(summary.code == "OPEN_OUT_OF_RANGE" for summary in result.fail_reasons)

    rows = conn.execute("SELECT COUNT(*) FROM raw_ohlcv").fetchone()[0]
    assert rows == 1


def test_batch_size_limit_violations_raise() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.RAW_OHLCV_TABLE.ensure(conn)

    config = IngestionConfig(max_batch_rows=1)

    records = [_make_record(), _make_record(supplier_symbol="000002")]

    with pytest.raises(IngestionConfigError):
        ingest(conn, records, provider="akshare", market="CN", config=config)
