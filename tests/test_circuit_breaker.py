"""Test circuit breaker implementation."""

import asyncio
import contextlib

import pytest

from vprism.core.exceptions import ProviderError
from vprism.core.patterns.circuitbreaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)


class TestCircuitBreaker:
    """Test circuit breaker."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=2, name="test_breaker")
        return CircuitBreaker(config)

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker: CircuitBreaker) -> None:
        async def success_func() -> str:
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_threshold(self, breaker: CircuitBreaker) -> None:
        async def failure_func() -> None:
            raise ProviderError("test failure", "test_provider")

        with pytest.raises(ProviderError):
            await breaker.call(failure_func)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1

        with pytest.raises(ProviderError):
            await breaker.call(failure_func)
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_open(self, breaker: CircuitBreaker) -> None:
        async def failure_func() -> None:
            raise ProviderError("test failure", "test_provider")

        for _ in range(2):
            with contextlib.suppress(ProviderError):
                await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN

        async def any_func() -> str:
            return "should not reach here"

        with pytest.raises(ProviderError) as exc_info:
            await breaker.call(any_func)
        assert "Circuit breaker OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_half_open_recovery(self, breaker: CircuitBreaker) -> None:
        async def failure_func() -> None:
            raise ProviderError("test failure", "test_provider")

        async def success_func() -> str:
            return "success"

        for _ in range(2):
            with contextlib.suppress(ProviderError):
                await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN
        await asyncio.sleep(0.2)

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 1

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure(self, breaker: CircuitBreaker) -> None:
        async def failure_func() -> None:
            raise ProviderError("test failure", "test_provider")

        for _ in range(2):
            with contextlib.suppress(ProviderError):
                await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN
        await asyncio.sleep(0.2)

        with pytest.raises(ProviderError):
            await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_reset(self, breaker: CircuitBreaker) -> None:
        async def failure_func() -> None:
            raise ProviderError("test failure", "test_provider")

        for _ in range(2):
            with contextlib.suppress(ProviderError):
                await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_get_state(self, breaker: CircuitBreaker) -> None:
        state = breaker.get_state()
        assert state["name"] == "test_breaker"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["success_count"] == 0
        assert state["last_failure_time"] is None


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    @pytest.fixture
    def registry(self) -> CircuitBreakerRegistry:
        return CircuitBreakerRegistry()

    @pytest.mark.asyncio
    async def test_get_or_create(self, registry: CircuitBreakerRegistry) -> None:
        breaker1 = await registry.get_or_create("test_breaker")
        breaker2 = await registry.get_or_create("test_breaker")
        assert breaker1 is breaker2
        assert breaker1.config.name == "test_breaker"

    @pytest.mark.asyncio
    async def test_get_or_create_with_config(self, registry: CircuitBreakerRegistry) -> None:
        config = CircuitBreakerConfig(failure_threshold=3, name="custom")
        breaker = await registry.get_or_create("custom_breaker", config)
        assert breaker.config.failure_threshold == 3
        assert breaker.config.name == "custom"

    def test_get_breaker(self, registry: CircuitBreakerRegistry) -> None:
        assert registry.get_breaker("non_existent") is None

    @pytest.mark.asyncio
    async def test_get_all_states(self, registry: CircuitBreakerRegistry) -> None:
        await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")
        states = registry.get_all_states()
        assert len(states) == 2
        assert "breaker1" in states
        assert "breaker2" in states
