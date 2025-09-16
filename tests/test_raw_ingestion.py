from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from vprism.core.data.ingestion.raw_ingestion import RawRecord, ingest_raw
from vprism.core.data.storage.schema import DatabaseSchema


def test_raw_ingestion_success():
    schema = DatabaseSchema(db_path=':memory:')
    conn = schema.conn
    base_ts = datetime.now(UTC).replace(microsecond=0)
    records = [
        RawRecord(
            symbol='000001',
            market='cn',
            ts=base_ts + timedelta(days=i),
            open=10 + i,
            high=11 + i,
            low=9 + i,
            close=10.5 + i,
            volume=1000 + i,
            source_system='akshare',
            upstream_origin='eastmoney',
        )
        for i in range(3)
    ]
    batch_id = str(uuid.uuid4())
    result = ingest_raw(conn, records, batch_id=batch_id)
    assert result.written_rows == 3
    assert result.rejected_rows == 0
    assert not result.issues
    cnt = conn.execute("SELECT COUNT(*) FROM raw_ohlcv_daily WHERE provider_batch_id = ?", [batch_id]).fetchone()[0]
    assert cnt == 3


def test_raw_ingestion_validation_failure():
    schema = DatabaseSchema(db_path=':memory:')
    conn = schema.conn
    ts = datetime.now(UTC).replace(microsecond=0)
    bad = RawRecord(symbol='000001', market='cn', ts=ts, open=10, high=9, low=8, close=9.5, volume=1000, source_system='akshare', upstream_origin='sina')
    batch_id = str(uuid.uuid4())
    result = ingest_raw(conn, [bad], batch_id=batch_id)
    assert result.written_rows == 0
    assert result.rejected_rows == 1
    assert any(i.code in {'OPEN_GT_HIGH', 'CLOSE_GT_HIGH', 'LOW_GT_HIGH'} for i in result.issues)
    cnt = conn.execute("SELECT COUNT(*) FROM raw_ohlcv_daily WHERE provider_batch_id = ?", [batch_id]).fetchone()[0]
    assert cnt == 0
