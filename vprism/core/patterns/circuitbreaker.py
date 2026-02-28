"""Circuit breaker pattern for provider fault tolerance."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from vprism.core.exceptions import ProviderError

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker state."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3
    expected_exception: type = ProviderError
    name: str = "default"


class CircuitBreaker:
    """Circuit breaker implementation."""

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.success_count = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Call function with circuit breaker protection.

        Lock is only held during state transitions, NOT during func execution.
        """
        # State check under lock
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise ProviderError(
                        f"Circuit breaker OPEN for {self.config.name}",
                        provider_name=self.config.name,
                        error_code="CIRCUIT_BREAKER_OPEN",
                        details={"remaining_time": self._get_remaining_time()},
                    )

        # Execute outside lock to allow concurrent calls
        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self._on_failure()
            raise
        else:
            async with self._lock:
                self._on_success()
            return result

    def _on_success(self) -> None:
        """Handle successful call (must be called under lock)."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call (must be called under lock)."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    def _get_remaining_time(self) -> float:
        if self.last_failure_time is None:
            return 0.0
        remaining = self.config.recovery_timeout - (time.time() - self.last_failure_time)
        return max(0.0, remaining)

    def get_state(self) -> dict[str, Any]:
        """Get circuit breaker state info."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "remaining_time": self._get_remaining_time() if self.state == CircuitState.OPEN else 0.0,
        }

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


# Global registry for named circuit breakers
class CircuitBreakerRegistry:
    """Registry for named circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
        """Get or create a named circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                if config is None:
                    config = CircuitBreakerConfig(name=name)
                self._breakers[name] = CircuitBreaker(config)
            return self._breakers[name]

    def get_breaker(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get all circuit breaker states."""
        return {name: b.get_state() for name, b in self._breakers.items()}


circuit_breaker_registry = CircuitBreakerRegistry()
