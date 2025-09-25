from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from vprism.core.data.schema import VPrismQualityMetricStatus
from vprism.core.exceptions import DriftComputationError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType

if TYPE_CHECKING:
    from datetime import datetime

PriceHistoryLoader = Callable[[str, MarketType, int], Sequence[DataPoint]]


@dataclass(frozen=True)
class DriftThresholds:
    """Warn/fail thresholds for absolute z-score drift classification."""

    warn: Decimal = Decimal("2")
    fail: Decimal = Decimal("3")

    def classify(self, zscore: Decimal) -> VPrismQualityMetricStatus:
        magnitude = abs(zscore)
        if magnitude >= self.fail:
            return VPrismQualityMetricStatus.FAIL
        if magnitude >= self.warn:
            return VPrismQualityMetricStatus.WARN
        return VPrismQualityMetricStatus.OK


@dataclass(frozen=True)
class DriftMetric:
    """Single drift metric value and associated status."""

    name: str
    value: Decimal
    status: VPrismQualityMetricStatus


@dataclass(frozen=True)
class DriftResult:
    """Computed drift metrics for a symbol/market window."""

    symbol: str
    market: MarketType
    window: int
    metrics: tuple[DriftMetric, ...]
    latest_timestamp: datetime


class DriftService:
    """Compute drift metrics and classify z-score based statuses."""

    def __init__(
        self,
        price_loader: PriceHistoryLoader,
        thresholds: DriftThresholds | None = None,
    ) -> None:
        self._price_loader = price_loader
        self._thresholds = thresholds or DriftThresholds()

    def compute(self, symbol: str, market: MarketType, window: int = 30) -> DriftResult:
        history = list(self._price_loader(symbol, market, window + 1))
        if len(history) < window + 1:
            raise DriftComputationError(
                "Drift computation requires at least window+1 data points.",
                symbol=symbol,
                market=market.value,
                details={"window": window, "received": len(history)},
            )

        sorted_history = sorted(history, key=lambda point: point.timestamp)
        window_history = sorted_history[-(window + 1) :]

        close_series = self._extract_series(symbol, market, window_history, "close_price")
        volume_series = self._extract_series(symbol, market, window_history, "volume")

        close_baseline = close_series[:-1]
        volume_baseline = volume_series[:-1]
        latest_point = window_history[-1]

        close_mean, close_std = self._compute_moments(close_baseline)
        volume_mean, volume_std = self._compute_moments(volume_baseline)

        close_zscore = self._compute_zscore(close_series[-1], close_mean, close_std)
        volume_zscore = self._compute_zscore(volume_series[-1], volume_mean, volume_std)

        metrics = (
            DriftMetric("close_mean", close_mean, VPrismQualityMetricStatus.OK),
            DriftMetric("close_std", close_std, VPrismQualityMetricStatus.OK),
            DriftMetric("volume_mean", volume_mean, VPrismQualityMetricStatus.OK),
            DriftMetric("volume_std", volume_std, VPrismQualityMetricStatus.OK),
            DriftMetric(
                "zscore_latest_close",
                close_zscore,
                self._thresholds.classify(close_zscore),
            ),
            DriftMetric(
                "zscore_latest_volume",
                volume_zscore,
                self._thresholds.classify(volume_zscore),
            ),
        )

        return DriftResult(
            symbol=symbol,
            market=market,
            window=window,
            metrics=metrics,
            latest_timestamp=latest_point.timestamp,
        )

    @staticmethod
    def _extract_series(
        symbol: str,
        market: MarketType,
        history: Sequence[DataPoint],
        field: str,
    ) -> list[Decimal]:
        series: list[Decimal] = []
        for point in history:
            value = getattr(point, field)
            if value is None:
                raise DriftComputationError(
                    f"Data point missing {field} for drift computation.",
                    symbol=symbol,
                    market=market.value,
                    details={"timestamp": point.timestamp.isoformat()},
                )
            if not isinstance(value, Decimal):
                value = Decimal(value)
            series.append(value)
        return series

    @staticmethod
    def _compute_moments(series: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
        if not series:
            return Decimal("0"), Decimal("0")

        decimal_series = list(series)
        mean = sum(decimal_series) / Decimal(len(decimal_series))
        if len(decimal_series) == 1:
            return mean, Decimal("0")

        variance = sum((value - mean) ** 2 for value in decimal_series) / Decimal(len(decimal_series) - 1)
        std = variance.sqrt() if variance != 0 else Decimal("0")
        return mean, std

    @staticmethod
    def _compute_zscore(value: Decimal, mean: Decimal, std: Decimal) -> Decimal:
        if std == 0:
            return Decimal("0")
        return (value - mean) / std


__all__ = ["DriftMetric", "DriftResult", "DriftService", "DriftThresholds"]
