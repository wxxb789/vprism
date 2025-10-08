from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vprism.core.services.shadow_diff import (
    DiffEngine,
    ShadowDiffResult,
    ShadowDiffStatus,
    ShadowRecord,
)


def _record(ts: tuple[int, int, int], close: float) -> ShadowRecord:
    return ShadowRecord(
        symbol="asset-1",
        market="cn",
        timestamp=datetime(*ts, tzinfo=UTC),
        close=close,
    )


def test_diff_engine_computes_statistics() -> None:
    engine = DiffEngine()
    primary = (
        _record((2024, 1, 1, 0, 0, 0), 10.0),
        _record((2024, 1, 2, 0, 0, 0), 12.0),
        _record((2024, 1, 3, 0, 0, 0), 11.5),
    )
    candidate = (
        _record((2024, 1, 1, 0, 0, 0), 10.1),
        _record((2024, 1, 2, 0, 0, 0), 12.12),
        _record((2024, 1, 3, 0, 0, 0), 11.46),
    )

    result = engine.compare(primary, candidate)

    assert isinstance(result, ShadowDiffResult)
    assert result.status is ShadowDiffStatus.PASS
    assert result.row_diff_pct == pytest.approx(0.0)
    assert result.gap_ratio == pytest.approx(0.0)
    assert result.price_diff_bp_p95 == pytest.approx(100.0, abs=1e-3)
    assert result.price_diff_bp_mean == pytest.approx(78.26, rel=1e-3)


def test_diff_engine_flags_failures() -> None:
    engine = DiffEngine()
    primary = (
        _record((2024, 1, 1, 0, 0, 0), 10.0),
        _record((2024, 1, 2, 0, 0, 0), 11.0),
    )
    candidate = (
        _record((2024, 1, 1, 0, 0, 0), 10.7),
    )

    result = engine.compare(primary, candidate)

    assert result.status is ShadowDiffStatus.FAIL
    assert result.row_diff_pct == pytest.approx(0.5)
    assert result.gap_ratio == pytest.approx(0.5)
    assert result.price_diff_bp_p95 >= 25.0
