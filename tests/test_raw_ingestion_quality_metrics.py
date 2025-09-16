from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from vprism.core.data.ingestion.raw_ingestion import RawRecord, ingest_raw
from vprism.core.data.storage.schema import DatabaseSchema


def test_raw_ingestion_quality_metrics_insert():
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
        for i in range(5)
    ]
    # introduce one anomaly (high < low)
    bad_ts = base_ts + timedelta(days=2)
    records[2] = RawRecord(
        symbol='000001',
        market='cn',
        ts=bad_ts,
        open=12,
        high=5,
        low=6,
        close=11,
        volume=2000,
        source_system='akshare',
        upstream_origin='eastmoney',
    )
    batch_id = str(uuid.uuid4())
    result = ingest_raw(conn, records, batch_id=batch_id)
    # if validation fails nothing should be written
    if result.written_rows == 0:
        assert result.rejected_rows == 5
        # quality metrics should not be inserted when batch rejected
        dq_rows = conn.execute("SELECT COUNT(*) FROM data_quality").fetchone()[0]
        assert dq_rows == 0
        return
    assert result.written_rows == 5
    dq_rows = conn.execute(
        "SELECT symbol, market, total_records, missing_records, anomaly_count, completeness_score, accuracy_score FROM data_quality"
    ).fetchall()
    assert dq_rows, 'data_quality row not inserted'
    row = dq_rows[0]
    assert row[0] == '000001'
    assert row[2] == 5
    # anomaly count should be >=1 due to high < low
    assert row[4] >= 1
    # completeness between 0 and 1
    assert 0 <= row[5] <= 1
    assert 0 <= row[6] <= 1
