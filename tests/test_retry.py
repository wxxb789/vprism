"""Test retry implementation."""

import pytest

from vprism.core.exceptions import ProviderError, RateLimitError
from vprism.core.patterns import (
    ExponentialBackoffRetry,
    ResilientExecutor,
    RetryConfig,
)
from vprism.core.patterns.retry import RetryState


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True
        assert config.exponential_base == 2.0
        assert ProviderError in config.retry_on_exceptions
        assert RateLimitError in config.skip_on_exceptions

    def test_custom_config(self) -> None:
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False,
            retry_on_exceptions=[ValueError],
            skip_on_exceptions=[TypeError],
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.jitter is False
        assert ValueError in config.retry_on_exceptions
        assert TypeError in config.skip_on_exceptions


class TestExponentialBackoffRetry:
    """Test exponential backoff retry."""

    @pytest.fixture
    def retry_instance(self) -> ExponentialBackoffRetry:
        config = RetryConfig(max_attempts=3, base_delay=0.1, max_delay=1.0)
        return ExponentialBackoffRetry(config)

    @pytest.mark.asyncio
    async def test_immediate_success_no_retry(self, retry_instance: ExponentialBackoffRetry) -> None:
        call_count = 0

        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_instance.execute(success_func)
        assert result == "success"
        assert call_count == 1
        assert retry_instance.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_failure(self, retry_instance: ExponentialBackoffRetry) -> None:
        call_count = 0

        async def failure_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderError(f"attempt {call_count}", "test_provider")
            return "success"

        result = await retry_instance.execute(failure_func)
        assert result == "success"
        assert call_count == 3
        assert retry_instance.attempt_count == 3

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self, retry_instance: ExponentialBackoffRetry) -> None:
        call_count = 0

        async def always_fail_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ProviderError(f"fail {call_count}", "test_provider")

        with pytest.raises(ProviderError) as exc_info:
            await retry_instance.execute(always_fail_func)

        assert call_count == 3
        assert retry_instance.state == RetryState.FAILED
        assert "fail 3" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_skip_retry_on_specific_exception(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.1, skip_on_exceptions=[ValueError])
        retry_instance = ExponentialBackoffRetry(config)
        call_count = 0

        async def skip_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("skip retry")

        with pytest.raises(ValueError):
            await retry_instance.execute(skip_func)

        assert call_count == 1

    def test_calculate_delay(self) -> None:
        config = RetryConfig(base_delay=1.0, max_delay=10.0, jitter=False)
        retry_instance = ExponentialBackoffRetry(config)

        assert retry_instance._calculate_delay(0) == 1.0
        assert retry_instance._calculate_delay(1) == 2.0
        assert retry_instance._calculate_delay(2) == 4.0
        assert retry_instance._calculate_delay(3) == 8.0
        assert retry_instance._calculate_delay(4) == 10.0

    def test_calculate_delay_with_jitter(self) -> None:
        config = RetryConfig(base_delay=1.0, max_delay=10.0, jitter=True)
        retry_instance = ExponentialBackoffRetry(config)

        delays = [retry_instance._calculate_delay(1) for _ in range(10)]
        assert all(1.8 <= d <= 2.2 for d in delays)

    def test_get_stats(self, retry_instance: ExponentialBackoffRetry) -> None:
        stats = retry_instance.get_stats()
        assert "attempts" in stats
        assert "max_attempts" in stats
        assert "total_delay" in stats
        assert "state" in stats
        assert "last_exception" in stats

    def test_reset(self, retry_instance: ExponentialBackoffRetry) -> None:
        retry_instance.attempt_count = 5
        retry_instance.total_delay = 10.0
        retry_instance.state = RetryState.FAILED

        retry_instance.reset()

        assert retry_instance.attempt_count == 0
        assert retry_instance.total_delay == 0.0
        assert retry_instance.state == RetryState.READY
        assert retry_instance.last_exception is None


class TestResilientExecutor:
    """Test resilient executor."""

    @pytest.mark.asyncio
    async def test_resilient_execution_success(self) -> None:
        executor = ResilientExecutor(
            "test_circuit",
            "test_retry",
            circuit_config={"failure_threshold": 2, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 2, "base_delay": 0.1},
        )

        async def success_func() -> str:
            return "success"

        result = await executor.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_resilient_execution_with_retry_and_circuit_breaker(self) -> None:
        call_count = 0

        async def sometimes_fail_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ProviderError(f"temp fail {call_count}", "test_provider")
            return f"final success {call_count}"

        executor = ResilientExecutor(
            "resilient_test",
            "resilient_retry",
            circuit_config={"failure_threshold": 3, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 3, "base_delay": 0.1},
        )

        result = await executor.execute(sometimes_fail_func)
        assert "final success" in result
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_resilient_execution_with_circuit_breaker_open(self) -> None:
        call_count = 0

        async def always_fail_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ProviderError(f"always fail {call_count}", "test_provider")

        executor = ResilientExecutor(
            "circuit_test",
            "retry_test",
            circuit_config={"failure_threshold": 2, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 2, "base_delay": 0.1},
        )

        with pytest.raises(ProviderError):
            await executor.execute(always_fail_func)

        with pytest.raises(ProviderError):
            await executor.execute(always_fail_func)
