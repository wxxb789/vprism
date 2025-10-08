from __future__ import annotations

import duckdb
import pytest
from datetime import UTC, datetime, date

from vprism.core.data import schema
from vprism.core.services.shadow import (
    DuckDBShadowRunWriter,
    ShadowDiffStatus,
    ShadowRunSummary,
)


def test_shadow_run_writer_persists_summary() -> None:
    conn = duckdb.connect(database=":memory:")
    schema.ensure_shadow_tables(conn)

    writer = DuckDBShadowRunWriter(conn)
    created_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    summary = ShadowRunSummary(
        run_id="run-1",
        start=date(2024, 1, 1),
        end=date(2024, 1, 5),
        asset="asset-1",
        markets=("cn", "us"),
        created_at=created_at,
        row_diff_pct=0.1,
        price_diff_bp_p95=12.0,
        gap_ratio=0.02,
        status=ShadowDiffStatus.WARN,
        sample_percent=25.0,
        lookback_days=30,
        force_full_run=False,
        primary_duration_ms=120.5,
        candidate_duration_ms=135.2,
    )

    writer(summary)

    rows = conn.execute("SELECT * FROM shadow_runs").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "run-1"
    assert row[1] == summary.start
    assert row[2] == summary.end
    assert row[3] == "asset-1"
    assert row[4] == "cn,us"
    assert row[6] == pytest.approx(0.1)
    assert row[7] == pytest.approx(12.0)
    assert row[8] == pytest.approx(0.02)
    assert row[9] == ShadowDiffStatus.WARN.value
    assert row[10] == pytest.approx(25.0)
    assert row[11] == 30
    assert row[12] is False
    assert row[13] == pytest.approx(120.5)
    assert row[14] == pytest.approx(135.2)
