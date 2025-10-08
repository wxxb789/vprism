from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from loguru import logger

from vprism.core.monitoring.performance import (
    SlowQueryLogger,
    SlowQueryThresholds,
)


class FakeTimer:
    def __init__(self, values: Iterator[float]) -> None:
        self._iterator = iter(values)

    def __call__(self) -> float:
        return next(self._iterator)


def test_track_emits_warning_when_threshold_exceeded() -> None:
    timer = FakeTimer([0.0, 0.25])
    slow_logger = SlowQueryLogger(
        thresholds=SlowQueryThresholds(p95_ms=100.0),
        time_source=timer,
    )
    records: list[dict[str, object]] = []

    def _capture(message: Any) -> None:
        snapshot = dict(message.record)
        snapshot["extra"] = dict(message.record.get("extra", {}))
        records.append(snapshot)

    handler_id = logger.add(_capture, level="WARNING")

    try:
        with slow_logger.track("quote_fetch", attributes={"supplier": "alpha"}):
            pass
    finally:
        logger.remove(handler_id)

    assert records, "expected a slow query warning to be emitted"
    log_record = records[0]
    assert log_record["message"] == "slow query detected for quote_fetch"
    assert isinstance(log_record.get("extra"), dict)


def test_observe_returns_non_slow_result() -> None:
    slow_logger = SlowQueryLogger(thresholds=SlowQueryThresholds(p95_ms=150.0))
    observation = slow_logger.observe(
        "quote_fetch",
        75.0,
        attributes={"supplier": "beta"},
    )

    assert observation.is_slow is False
    assert observation.duration_ms == pytest.approx(75.0)
    assert observation.threshold_ms == 150.0
    assert observation.attributes == {"supplier": "beta"}
