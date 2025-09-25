from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from vprism.core.data.schema import VPrismQualityMetricStatus
from vprism.core.services.quality.gap_detector import QualityMetricRow
from vprism.core.services.quality.thresholds import (
    VPrismMetricThresholds,
    vprism_classify_metric,
)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from vprism.core.services.quality.gap_detector import DuckDBQualityMetricWriter


DEFAULT_DUPLICATE_THRESHOLDS = VPrismMetricThresholds(warn=1, fail=3)


VPrismDuplicateMetricWriter = Callable[[QualityMetricRow], None]


@dataclass(frozen=True)
class VPrismDuplicateDetectionResult:
    """Result of duplicate evaluation for a single symbol."""

    duplicates: tuple[tuple[date, int], ...]
    duplicate_total: int
    status: VPrismQualityMetricStatus


class VPrismDuplicateDetector:
    """Detect duplicate trading days and persist metrics."""

    def __init__(
        self,
        metric_writer: VPrismDuplicateMetricWriter,
        duplicate_thresholds: VPrismMetricThresholds | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._metric_writer = metric_writer
        self._thresholds = duplicate_thresholds or DEFAULT_DUPLICATE_THRESHOLDS
        self._clock = clock or (lambda: datetime.now(UTC))

    def evaluate(
        self,
        *,
        market: str,
        symbol: str,
        observed_timestamps: Sequence[date | datetime] | Iterable[date | datetime],
        run_id: str,
        metric_date: date | None = None,
    ) -> VPrismDuplicateDetectionResult:
        """Compute duplicate counts for the provided timestamps."""

        normalized = self._normalize_dates(observed_timestamps)
        counter = Counter(normalized)
        duplicates = tuple(sorted((day, count) for day, count in counter.items() if count > 1))
        duplicate_total = int(sum(count - 1 for _, count in duplicates))
        status = vprism_classify_metric(float(duplicate_total), self._thresholds)

        metric_row = QualityMetricRow(
            date=metric_date or (max(normalized) if normalized else datetime.now(UTC).date()),
            market=market,
            supplier_symbol=symbol,
            metric="duplicate_count",
            value=float(duplicate_total),
            status=status,
            run_id=run_id,
            created_at=self._clock(),
        )
        self._metric_writer(metric_row)

        return VPrismDuplicateDetectionResult(
            duplicates=duplicates,
            duplicate_total=duplicate_total,
            status=status,
        )

    @staticmethod
    def _normalize_dates(
        timestamps: Sequence[date | datetime] | Iterable[date | datetime],
    ) -> list[date]:
        normalized: list[date] = []
        for value in timestamps:
            current = value.date() if isinstance(value, datetime) else value
            normalized.append(current)
        return normalized


__all__ = [
    "DEFAULT_DUPLICATE_THRESHOLDS",
    "VPrismDuplicateDetectionResult",
    "VPrismDuplicateDetector",
    "VPrismDuplicateMetricWriter",
]
