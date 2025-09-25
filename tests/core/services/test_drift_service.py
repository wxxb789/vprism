from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from vprism.core.exceptions import DriftComputationError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import MarketType
from vprism.core.services.drift import DriftService, DriftThresholds

if TYPE_CHECKING:
    from collections.abc import Iterable


def _series(
    start: datetime,
    values: Iterable[tuple[str, str]],
) -> list[DataPoint]:
    points: list[DataPoint] = []
    for index, (close_value, volume_value) in enumerate(values):
        points.append(
            DataPoint(
                symbol="000001",
                market=MarketType.CN,
                timestamp=start + timedelta(days=index),
                close_price=Decimal(close_value),
                volume=Decimal(volume_value),
            )
        )
    return points


def test_compute_warn_status_for_close() -> None:
    base_time = datetime(2024, 1, 1)
    history = _series(
        base_time,
        [
            ("10", "100"),
            ("11", "100"),
            ("12", "100"),
            ("13", "100"),
        ],
    )

    service = DriftService(lambda *_: history)
    result = service.compute(symbol="000001", market=MarketType.CN, window=3)

    metrics = {metric.name: metric for metric in result.metrics}
    assert metrics["close_mean"].value == Decimal("11")
    assert metrics["close_std"].value == Decimal("1")
    assert metrics["zscore_latest_close"].status.value == "WARN"
    assert metrics["zscore_latest_close"].value == Decimal("2")
    assert metrics["zscore_latest_volume"].status.value == "OK"


def test_compute_fail_status_for_volume() -> None:
    base_time = datetime(2024, 1, 1)
    history = _series(
        base_time,
        [
            ("10", "100"),
            ("10", "110"),
            ("10", "90"),
            ("10", "120"),
        ],
    )

    service = DriftService(lambda *_: history)
    result = service.compute(symbol="000001", market=MarketType.CN, window=3)

    metrics = {metric.name: metric for metric in result.metrics}
    assert metrics["volume_mean"].value == Decimal("100")
    assert metrics["volume_std"].value == Decimal("10")
    assert metrics["zscore_latest_volume"].status.value == "WARN"

    thresholds = DriftThresholds(warn=Decimal("1"), fail=Decimal("2"))
    service_custom = DriftService(lambda *_: history, thresholds=thresholds)
    custom_metrics = {
        metric.name: metric
        for metric in service_custom.compute(symbol="000001", market=MarketType.CN, window=3).metrics
    }
    assert custom_metrics["zscore_latest_volume"].status.value == "FAIL"


def test_zero_standard_deviation_returns_zero_zscore() -> None:
    base_time = datetime(2024, 1, 1)
    history = _series(
        base_time,
        [
            ("10", "100"),
            ("10", "100"),
            ("10", "100"),
            ("10", "100"),
        ],
    )

    service = DriftService(lambda *_: history)
    result = service.compute(symbol="000001", market=MarketType.CN, window=3)

    metrics = {metric.name: metric for metric in result.metrics}
    assert metrics["zscore_latest_close"].value == Decimal("0")
    assert metrics["zscore_latest_close"].status.value == "OK"


def test_raises_when_insufficient_history() -> None:
    base_time = datetime(2024, 1, 1)
    history = _series(
        base_time,
        [
            ("10", "100"),
            ("10", "100"),
        ],
    )

    service = DriftService(lambda *_: history)

    with pytest.raises(DriftComputationError):
        service.compute(symbol="000001", market=MarketType.CN, window=3)
