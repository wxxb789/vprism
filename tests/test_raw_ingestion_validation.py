from __future__ import annotations

from datetime import datetime, timedelta

from vprism.core.data.ingestion.raw_ingestion import RawRecord, validate_records


def test_validate_records_duplicate_and_non_monotonic():
    base_ts = datetime(2024, 1, 1, 0, 0, 0)
    records = [
        RawRecord(symbol="000001", market="CN", ts=base_ts, open=1, high=2, low=1, close=1.5, volume=10, source_system="akshare"),
        RawRecord(symbol="000001", market="CN", ts=base_ts, open=1, high=2, low=1, close=1.5, volume=10, source_system="akshare"),  # duplicate
        RawRecord(
            symbol="000001",
            market="CN",
            ts=base_ts - timedelta(days=1),
            open=1,
            high=2,
            low=1,
            close=1.5,
            volume=10,
            source_system="akshare",
        ),  # non-monotonic
    ]
    issues = validate_records(records)
    codes = {i.code for i in issues}
    assert "DUPLICATE_ROW" in codes
    assert "NON_MONOTONIC" in codes


def test_validate_records_price_relationships():
    base_ts = datetime(2024, 1, 1)
    records = [
        RawRecord(
            symbol="000001",
            market="CN",
            ts=base_ts,
            open=3,
            high=2,
            low=1,
            close=1.5,
            volume=10,
            source_system="akshare",
        ),  # open > high
        RawRecord(
            symbol="000001",
            market="CN",
            ts=base_ts + timedelta(days=1),
            open=1,
            high=2,
            low=1.5,
            close=3,
            volume=10,
            source_system="akshare",
        ),  # close > high
        RawRecord(
            symbol="000001",
            market="CN",
            ts=base_ts + timedelta(days=2),
            open=1,
            high=2,
            low=3,
            close=1.5,
            volume=10,
            source_system="akshare",
        ),  # low > high
    ]
    issues = validate_records(records)
    code_counts = {c.code: 0 for c in [*issues]}
    for i in issues:
        code_counts[i.code] = code_counts.get(i.code, 0) + 1
    assert "OPEN_GT_HIGH" in code_counts
    assert "CLOSE_GT_HIGH" in code_counts
    assert "LOW_GT_HIGH" in code_counts
