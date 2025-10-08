"""Shadow diff computation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import ceil
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ShadowRecord:
    """Normalized representation of a row returned by a query path."""

    symbol: str
    market: str
    timestamp: datetime
    close: float

    def key(self) -> tuple[str, str, datetime]:
        return self.symbol, self.market, self.timestamp


class ShadowDiffStatus(str, Enum):
    """Classification of diff health."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ShadowDiffThresholds:
    """Thresholds controlling diff status classification."""

    row_diff_warn: float = 0.02
    row_diff_fail: float = 0.1
    price_diff_bp_p95_warn: float = 150.0
    price_diff_bp_p95_fail: float = 300.0
    gap_ratio_warn: float = 0.02
    gap_ratio_fail: float = 0.1


@dataclass(frozen=True)
class ShadowDiffResult:
    """Aggregated diff metrics for a shadow comparison."""

    row_diff_pct: float
    price_diff_bp_mean: float
    price_diff_bp_p95: float
    gap_ratio: float
    status: ShadowDiffStatus


class DiffEngine:
    """Compute metric deltas between two query results."""

    def __init__(self, thresholds: ShadowDiffThresholds | None = None) -> None:
        self._thresholds = thresholds or ShadowDiffThresholds()

    def compare(
        self,
        primary_rows: Sequence[ShadowRecord],
        candidate_rows: Sequence[ShadowRecord],
    ) -> ShadowDiffResult:
        primary_map = {record.key(): record for record in primary_rows}
        candidate_map = {record.key(): record for record in candidate_rows}

        row_diff_pct = self._compute_row_diff_pct(primary_map, candidate_map)
        gap_ratio = self._compute_gap_ratio(primary_map, candidate_map)
        bp_diffs = list(self._iter_basis_point_diffs(primary_map, candidate_map))
        price_diff_bp_mean = sum(bp_diffs) / len(bp_diffs) if bp_diffs else 0.0
        price_diff_bp_p95 = self._percentile(bp_diffs, 95)

        status = self._classify(row_diff_pct, price_diff_bp_p95, gap_ratio)
        return ShadowDiffResult(
            row_diff_pct=row_diff_pct,
            price_diff_bp_mean=price_diff_bp_mean,
            price_diff_bp_p95=price_diff_bp_p95,
            gap_ratio=gap_ratio,
            status=status,
        )

    def _classify(
        self,
        row_diff_pct: float,
        price_diff_bp_p95: float,
        gap_ratio: float,
    ) -> ShadowDiffStatus:
        thresholds = self._thresholds
        if (
            row_diff_pct >= thresholds.row_diff_fail
            or price_diff_bp_p95 >= thresholds.price_diff_bp_p95_fail
            or gap_ratio >= thresholds.gap_ratio_fail
        ):
            return ShadowDiffStatus.FAIL
        if (
            row_diff_pct >= thresholds.row_diff_warn
            or price_diff_bp_p95 >= thresholds.price_diff_bp_p95_warn
            or gap_ratio >= thresholds.gap_ratio_warn
        ):
            return ShadowDiffStatus.WARN
        return ShadowDiffStatus.PASS

    @staticmethod
    def _compute_row_diff_pct(
        primary_map: dict[tuple[str, str, datetime], ShadowRecord],
        candidate_map: dict[tuple[str, str, datetime], ShadowRecord],
    ) -> float:
        primary_count = len(primary_map)
        candidate_count = len(candidate_map)
        if primary_count == 0:
            return 0.0 if candidate_count == 0 else 1.0
        return abs(primary_count - candidate_count) / primary_count

    @staticmethod
    def _compute_gap_ratio(
        primary_map: dict[tuple[str, str, datetime], ShadowRecord],
        candidate_map: dict[tuple[str, str, datetime], ShadowRecord],
    ) -> float:
        primary_count = len(primary_map)
        if primary_count == 0:
            return 0.0
        missing = sum(1 for key in primary_map if key not in candidate_map)
        return missing / primary_count

    @staticmethod
    def _iter_basis_point_diffs(
        primary_map: dict[tuple[str, str, datetime], ShadowRecord],
        candidate_map: dict[tuple[str, str, datetime], ShadowRecord],
    ) -> Iterable[float]:
        for key, primary_record in primary_map.items():
            candidate_record = candidate_map.get(key)
            if candidate_record is None:
                continue
            if primary_record.close == 0:
                yield 0.0
                continue
            diff_ratio = abs(candidate_record.close - primary_record.close) / abs(primary_record.close)
            yield diff_ratio * 10000

    @staticmethod
    def _percentile(values: Sequence[float], percentile: int) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        rank = ceil((percentile / 100) * len(sorted_values))
        index = min(max(rank - 1, 0), len(sorted_values) - 1)
        return sorted_values[index]


__all__ = [
    "DiffEngine",
    "ShadowDiffResult",
    "ShadowDiffStatus",
    "ShadowDiffThresholds",
    "ShadowRecord",
]
