"""Gap detection service writing metrics into the quality schema."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from vprism.core.data.schema import (
    VPrismQualityMetricStatus,
    vprism_quality_metrics_table,
)
from vprism.core.services.quality.thresholds import (
    VPrismMetricThresholds,
    vprism_classify_metric,
)

GapMetricWriter = Callable[["QualityMetricRow"], None]

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from vprism.core.services.calendars import VPrismTradingCalendarProvider


@dataclass(frozen=True)
class QualityMetricRow:
    """Row persisted into the ``quality_metrics`` table."""

    date: date
    market: str
    supplier_symbol: str
    metric: str
    value: float
    status: VPrismQualityMetricStatus
    run_id: str
    created_at: datetime


@dataclass(frozen=True)
class GapDetectionResult:
    """Computed gap metrics for the supplied time window."""

    expected_days: tuple[date, ...]
    observed_days: tuple[date, ...]
    missing_days: tuple[date, ...]
    gap_ratio: float
    status: VPrismQualityMetricStatus


DEFAULT_GAP_RATIO_THRESHOLDS = VPrismMetricThresholds(warn=0.002, fail=0.005)


class GapDetector:
    """Detects missing trading days and records gap metrics."""

    def __init__(
        self,
        calendar_provider: VPrismTradingCalendarProvider,
        metric_writer: GapMetricWriter,
        gap_thresholds: VPrismMetricThresholds | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._calendar_provider = calendar_provider
        self._metric_writer = metric_writer
        self._thresholds = gap_thresholds or DEFAULT_GAP_RATIO_THRESHOLDS
        self._clock = clock or (lambda: datetime.now(UTC))

    def evaluate(
        self,
        *,
        market: str,
        symbol: str,
        start: date,
        end: date,
        observed_timestamps: Sequence[date | datetime] | Iterable[date | datetime],
        run_id: str,
        metric_date: date | None = None,
    ) -> GapDetectionResult:
        """Compute gap metrics for the provided parameters and persist them."""

        expected_days = tuple(self._calendar_provider.vprism_get_trading_days(market, start, end))
        observed_days = self._normalize_observed(observed_timestamps, start, end)
        missing_days = tuple(day for day in expected_days if day not in observed_days)

        gap_ratio = self._compute_gap_ratio(len(expected_days), len(missing_days))
        status = vprism_classify_metric(gap_ratio, self._thresholds)

        created_at = self._clock()
        metric_row = QualityMetricRow(
            date=metric_date or end,
            market=market,
            supplier_symbol=symbol,
            metric="gap_ratio",
            value=gap_ratio,
            status=status,
            run_id=run_id,
            created_at=created_at,
        )
        self._metric_writer(metric_row)

        return GapDetectionResult(
            expected_days=expected_days,
            observed_days=tuple(sorted(observed_days)),
            missing_days=missing_days,
            gap_ratio=gap_ratio,
            status=status,
        )

    @staticmethod
    def _normalize_observed(
        timestamps: Sequence[date | datetime] | Iterable[date | datetime],
        start: date,
        end: date,
    ) -> set[date]:
        observed: set[date] = set()
        for value in timestamps:
            current_date = value.date() if isinstance(value, datetime) else value
            if start <= current_date <= end:
                observed.add(current_date)
        return observed

    @staticmethod
    def _compute_gap_ratio(expected_count: int, missing_count: int) -> float:
        if expected_count == 0:
            return 0.0
        return missing_count / expected_count


class DuckDBQualityMetricWriter:
    """Persist quality metric rows into DuckDB."""

    def __init__(self, connection: DuckDBPyConnection) -> None:
        self._connection = connection
        vprism_quality_metrics_table.ensure(connection)

    def __call__(self, row: QualityMetricRow) -> None:
        self._connection.execute(
            """
            INSERT INTO quality_metrics
            (date, market, supplier_symbol, metric, value, status, run_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.date,
                row.market,
                row.supplier_symbol,
                row.metric,
                row.value,
                row.status.value,
                row.run_id,
                row.created_at,
            ],
        )


__all__ = [
    "DEFAULT_GAP_RATIO_THRESHOLDS",
    "DuckDBQualityMetricWriter",
    "GapDetectionResult",
    "GapDetector",
    "QualityMetricRow",
]
