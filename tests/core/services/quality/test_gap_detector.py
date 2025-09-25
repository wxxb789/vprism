from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from vprism.core.data.schema import VPrismQualityMetricStatus, vprism_quality_metrics_table
from vprism.core.services.calendars import VPrismTradingCalendarProvider
from vprism.core.services.quality.gap_detector import (
    DEFAULT_GAP_RATIO_THRESHOLDS,
    DuckDBQualityMetricWriter,
    GapDetector,
)


@pytest.fixture()
def duckdb_connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(database=":memory:")
    vprism_quality_metrics_table.ensure(connection)
    return connection


def _fixed_clock() -> datetime:
    return datetime(2024, 1, 6, 12, tzinfo=UTC)


def test_gap_detector_records_ok_metric(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    provider = VPrismTradingCalendarProvider()
    detector = GapDetector(
        provider,
        DuckDBQualityMetricWriter(duckdb_connection),
        clock=_fixed_clock,
    )

    observed = [
        datetime(2024, 1, 1, 10, tzinfo=UTC),
        datetime(2024, 1, 2, 10, tzinfo=UTC),
        datetime(2024, 1, 3, 10, tzinfo=UTC),
        datetime(2024, 1, 4, 10, tzinfo=UTC),
        datetime(2024, 1, 5, 10, tzinfo=UTC),
    ]

    result = detector.evaluate(
        market="cn",
        symbol="000001",
        start=date(2024, 1, 1),
        end=date(2024, 1, 5),
        observed_timestamps=observed,
        run_id="run-ok",
    )

    assert result.gap_ratio == pytest.approx(0.0)
    assert result.status is VPrismQualityMetricStatus.OK
    assert result.missing_days == ()

    row = duckdb_connection.execute(
        """
        SELECT date, market, supplier_symbol, metric, value, status, run_id, created_at
        FROM quality_metrics
        """
    ).fetchone()

    assert row is not None
    assert row[0] == date(2024, 1, 5)
    assert row[1] == "cn"
    assert row[2] == "000001"
    assert row[3] == "gap_ratio"
    assert row[4] == pytest.approx(0.0)
    assert row[5] == "OK"
    assert row[6] == "run-ok"
    stored_created_at = row[7]
    if stored_created_at.tzinfo is None:
        stored_created_at = stored_created_at.replace(tzinfo=UTC)
    assert stored_created_at == _fixed_clock()


def test_gap_detector_records_fail_when_missing_days(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    provider = VPrismTradingCalendarProvider()
    detector = GapDetector(
        provider,
        DuckDBQualityMetricWriter(duckdb_connection),
        gap_thresholds=DEFAULT_GAP_RATIO_THRESHOLDS,
        clock=_fixed_clock,
    )

    observed = [
        date(2024, 1, 1),
        date(2024, 1, 3),
        date(2024, 1, 5),
    ]

    result = detector.evaluate(
        market="cn",
        symbol="000002",
        start=date(2024, 1, 1),
        end=date(2024, 1, 5),
        observed_timestamps=observed,
        run_id="run-fail",
    )

    assert result.missing_days == (date(2024, 1, 2), date(2024, 1, 4))
    assert result.gap_ratio == pytest.approx(2 / 5)
    assert result.status is VPrismQualityMetricStatus.FAIL

    row = duckdb_connection.execute(
        """
        SELECT metric, value, status, run_id
        FROM quality_metrics
        WHERE supplier_symbol = ?
        """,
        ["000002"],
    ).fetchone()

    assert row[0] == "gap_ratio"
    assert row[1] == pytest.approx(2 / 5)
    assert row[2] == "FAIL"
    assert row[3] == "run-fail"
