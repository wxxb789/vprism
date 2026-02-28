"""Retry with exponential backoff."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from vprism.core.exceptions import ProviderError, RateLimitError

T = TypeVar("T")


class RetryState(Enum):
    """Retry state."""

    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RetryConfig:
    """Retry configuration."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_exceptions: list[type] = field(default_factory=lambda: [ProviderError])
    skip_on_exceptions: list[type] = field(default_factory=lambda: [RateLimitError])


class ExponentialBackoffRetry:
    """Exponential backoff retry implementation."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt_count = 0
        self.total_delay = 0.0
        self.state = RetryState.READY
        self.last_exception: Exception | None = None

    async def execute(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Execute function with retry logic."""
        self.state = RetryState.RUNNING
        self.attempt_count = 0
        self.total_delay = 0.0

        while self.attempt_count < self.config.max_attempts:
            try:
                self.attempt_count += 1
                result = await func(*args, **kwargs)
                self.state = RetryState.COMPLETED
                return result
            except Exception as e:
                self.last_exception = e

                if any(isinstance(e, t) for t in self.config.skip_on_exceptions):
                    self.state = RetryState.FAILED
                    raise

                should_retry = any(isinstance(e, t) for t in self.config.retry_on_exceptions)
                if not should_retry or self.attempt_count >= self.config.max_attempts:
                    self.state = RetryState.FAILED
                    raise

                delay = self._calculate_delay(self.attempt_count - 1)
                await asyncio.sleep(delay)
                self.total_delay += delay

        if self.last_exception:
            raise self.last_exception
        raise RuntimeError("Retry loop completed without success or exception.")

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.config.base_delay * (self.config.exponential_base**attempt)
        if self.config.jitter:
            jitter_range = min(delay * 0.1, 1.0)
            delay += random.uniform(-jitter_range, jitter_range)
        return min(delay, self.config.max_delay)

    def get_stats(self) -> dict[str, Any]:
        """Get retry statistics."""
        return {
            "attempts": self.attempt_count,
            "max_attempts": self.config.max_attempts,
            "total_delay": self.total_delay,
            "state": self.state.value,
            "last_exception": str(self.last_exception) if self.last_exception else None,
        }

    def reset(self) -> None:
        """Reset retry state."""
        self.attempt_count = 0
        self.total_delay = 0.0
        self.state = RetryState.READY
        self.last_exception = None
