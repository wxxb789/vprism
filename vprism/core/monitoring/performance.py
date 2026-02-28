"""Performance monitoring utilities for query latency thresholds."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from loguru import logger


@dataclass(frozen=True)
class SlowQueryThresholds:
    """Configuration describing slow query alert thresholds."""

    p95_ms: float = 500.0

    def is_slow(self, duration_ms: float) -> bool:
        """Return ``True`` when ``duration_ms`` exceeds the configured threshold."""

        return duration_ms >= self.p95_ms


@dataclass(frozen=True)
class SlowQueryObservation:
    """Represents a single slow query latency observation."""

    operation: str
    duration_ms: float
    threshold_ms: float
    attributes: Mapping[str, Any]
    is_slow: bool


class SlowQueryLogger:
    """Monitor query latency and emit warnings when crossing thresholds."""

    def __init__(
        self,
        *,
        thresholds: SlowQueryThresholds | None = None,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self._thresholds = thresholds or SlowQueryThresholds()
        self._time_source = time_source or perf_counter

    @contextmanager
    def track(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[None]:
        """Context manager measuring a block and logging slow executions."""

        start = self._time_source()
        try:
            yield
        finally:
            duration_ms = (self._time_source() - start) * 1000.0
            self.observe(operation, duration_ms, attributes=attributes)

    def observe(
        self,
        operation: str,
        duration_ms: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> SlowQueryObservation:
        """Record an explicit latency observation and emit warnings when slow."""

        payload = dict(attributes or {})
        is_slow = self._thresholds.is_slow(duration_ms)
        observation = SlowQueryObservation(
            operation=operation,
            duration_ms=duration_ms,
            threshold_ms=self._thresholds.p95_ms,
            attributes=payload,
            is_slow=is_slow,
        )
        if is_slow:
            logger.warning(
                f"slow query detected for {operation}",
                extra={
                    "operation": operation,
                    "duration_ms": round(duration_ms, 3),
                    "threshold_ms": self._thresholds.p95_ms,
                    **payload,
                },
            )
        return observation


__all__ = [
    "SlowQueryLogger",
    "SlowQueryObservation",
    "SlowQueryThresholds",
]
