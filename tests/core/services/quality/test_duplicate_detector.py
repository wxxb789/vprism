import duckdb
import pytest

from datetime import UTC, date, datetime

from vprism.core.data.schema import vprism_quality_metrics_table
from vprism.core.services.quality.duplicate_detector import (
    DEFAULT_DUPLICATE_THRESHOLDS,
    VPrismDuplicateDetector,
)
from vprism.core.services.quality.gap_detector import DuckDBQualityMetricWriter
from vprism.core.data.schema import VPrismQualityMetricStatus


@pytest.fixture()
def duckdb_connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(database=":memory:")
    vprism_quality_metrics_table.ensure(connection)
    return connection


def _fixed_clock() -> datetime:
    return datetime(2024, 3, 1, 9, tzinfo=UTC)


def test_duplicate_detector_records_fail_metric(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    detector = VPrismDuplicateDetector(
        DuckDBQualityMetricWriter(duckdb_connection),
        DEFAULT_DUPLICATE_THRESHOLDS,
        clock=_fixed_clock,
    )
    observed = [
        datetime(2024, 1, 1, 9, tzinfo=UTC),
        datetime(2024, 1, 1, 10, tzinfo=UTC),
        datetime(2024, 1, 2, 9, tzinfo=UTC),
        datetime(2024, 1, 2, 10, tzinfo=UTC),
        datetime(2024, 1, 2, 11, tzinfo=UTC),
    ]

    result = detector.evaluate(
        market="cn",
        symbol="000001",
        observed_timestamps=observed,
        run_id="run-duplicates",
        metric_date=date(2024, 1, 2),
    )

    assert result.duplicate_total == 3
    assert result.status is VPrismQualityMetricStatus.FAIL
    assert result.duplicates == (
        (date(2024, 1, 1), 2),
        (date(2024, 1, 2), 3),
    )

    row = duckdb_connection.execute(
        """
        SELECT value, status, run_id, created_at
        FROM quality_metrics
        WHERE metric = 'duplicate_count'
        """
    ).fetchone()

    assert row is not None
    assert row[0] == pytest.approx(3.0)
    assert row[1] == "FAIL"
    assert row[2] == "run-duplicates"
    stored_time = row[3]
    if stored_time.tzinfo is None:
        stored_time = stored_time.replace(tzinfo=UTC)
    assert stored_time == _fixed_clock()


def test_duplicate_detector_records_ok_metric_when_unique(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    detector = VPrismDuplicateDetector(
        DuckDBQualityMetricWriter(duckdb_connection),
        clock=_fixed_clock,
    )
    observed = [
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
    ]

    result = detector.evaluate(
        market="cn",
        symbol="000002",
        observed_timestamps=observed,
        run_id="run-unique",
        metric_date=date(2024, 1, 3),
    )

    assert result.duplicate_total == 0
    assert result.status is VPrismQualityMetricStatus.OK
    assert result.duplicates == ()

    row = duckdb_connection.execute(
        """
        SELECT value, status, run_id
        FROM quality_metrics
        WHERE supplier_symbol = ?
        """,
        ["000002"],
    ).fetchone()

    assert row is not None
    assert row[0] == pytest.approx(0.0)
    assert row[1] == "OK"
    assert row[2] == "run-unique"
