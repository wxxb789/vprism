"""测试重试机制实现."""

import pytest

from core.exceptions import ProviderError, RateLimitError
from core.patterns import (
    ExponentialBackoffRetry,
    ResilientExecutor,
    RetryConfig,
    RetryRegistry,
    retry,
)
from core.patterns.retry import RetryState


class TestRetryConfig:
    """测试重试配置."""

    def test_default_config(self):
        """测试默认配置."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.multiplier == 2.0
        assert config.jitter is True
        assert config.exponential_base == 2.0
        assert ProviderError in config.retry_on_exceptions
        assert RateLimitError in config.skip_on_exceptions

    def test_custom_config(self):
        """测试自定义配置."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            multiplier=1.5,
            jitter=False,
            retry_on_exceptions=[ValueError],
            skip_on_exceptions=[TypeError],
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.multiplier == 1.5
        assert config.jitter is False
        assert ValueError in config.retry_on_exceptions
        assert TypeError in config.skip_on_exceptions


class TestExponentialBackoffRetry:
    """测试指数退避重试."""

    @pytest.fixture
    def retry_instance(self):
        """创建重试实例."""
        config = RetryConfig(max_attempts=3, base_delay=0.1, max_delay=1.0, multiplier=2.0)
        return ExponentialBackoffRetry(config)

    @pytest.mark.asyncio
    async def test_successful_execution(self, retry_instance):
        """测试成功执行."""

        async def success_func():
            return "success"

        result = await retry_instance.execute(success_func)
        assert result == "success"
        assert retry_instance.state == RetryState.COMPLETED
        assert retry_instance.attempt_count == 1

    @pytest.mark.asyncio
    async def test_immediate_success_no_retry(self, retry_instance):
        """测试立即成功，不重试."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_instance.execute(success_func)
        assert result == "success"
        assert call_count == 1
        assert retry_instance.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_failure(self, retry_instance):
        """测试失败后的重试."""
        call_count = 0

        async def failure_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderError(f"尝试 {call_count}", "test_provider")
            return "success"

        result = await retry_instance.execute(failure_func)
        assert result == "success"
        assert call_count == 3
        assert retry_instance.attempt_count == 3

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self, retry_instance):
        """测试所有重试都失败."""
        call_count = 0

        async def always_fail_func():
            nonlocal call_count
            call_count += 1
            raise ProviderError(f"失败 {call_count}", "test_provider")

        with pytest.raises(ProviderError) as exc_info:
            await retry_instance.execute(always_fail_func)

        assert call_count == 3  # 原始调用 + 2次重试
        assert retry_instance.state == RetryState.FAILED
        assert "失败 3" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_skip_retry_on_specific_exception(self):
        """测试特定异常跳过重试."""
        config = RetryConfig(max_attempts=3, base_delay=0.1, skip_on_exceptions=[ValueError])
        retry_instance = ExponentialBackoffRetry(config)

        call_count = 0

        async def skip_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("跳过重试")

        with pytest.raises(ValueError):
            await retry_instance.execute(skip_func)

        assert call_count == 1  # 只调用一次，不重试

    def test_calculate_delay(self):
        """测试延迟计算."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, multiplier=2.0, jitter=False)
        retry_instance = ExponentialBackoffRetry(config)

        assert retry_instance._calculate_delay(0) == 1.0
        assert retry_instance._calculate_delay(1) == 2.0
        assert retry_instance._calculate_delay(2) == 4.0
        assert retry_instance._calculate_delay(3) == 8.0
        assert retry_instance._calculate_delay(4) == 10.0  # 达到最大值

    def test_calculate_delay_with_jitter(self):
        """测试带抖动的延迟计算."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, multiplier=2.0, jitter=True)
        retry_instance = ExponentialBackoffRetry(config)

        # 多次调用，验证抖动效果
        delays = [retry_instance._calculate_delay(1) for _ in range(10)]
        assert all(1.8 <= d <= 2.2 for d in delays)

    def test_get_stats(self, retry_instance):
        """测试获取统计信息."""
        stats = retry_instance.get_stats()

        assert "attempts" in stats
        assert "max_attempts" in stats
        assert "total_delay" in stats
        assert "state" in stats
        assert "last_exception" in stats

    def test_reset(self, retry_instance):
        """测试重置."""
        retry_instance.attempt_count = 5
        retry_instance.total_delay = 10.0
        retry_instance.state = RetryState.FAILED

        retry_instance.reset()

        assert retry_instance.attempt_count == 0
        assert retry_instance.total_delay == 0.0
        assert retry_instance.state == RetryState.READY
        assert retry_instance.last_exception is None


class TestRetryRegistry:
    """测试重试注册表."""

    @pytest.fixture
    def registry(self):
        """创建注册表实例."""
        return RetryRegistry()

    @pytest.mark.asyncio
    async def test_get_or_create(self, registry):
        """测试获取或创建重试实例."""
        retry1 = await registry.get_or_create("test_retry")
        retry2 = await registry.get_or_create("test_retry")

        assert retry1 is retry2

    @pytest.mark.asyncio
    async def test_get_or_create_with_config(self, registry):
        """测试获取或创建带配置的重试实例."""
        config = RetryConfig(max_attempts=5)
        retry_instance = await registry.get_or_create("custom_retry", config)

        assert retry_instance.config.max_attempts == 5

    def test_get_retry(self, registry):
        """测试获取指定重试实例."""
        assert registry.get_retry("non_existent") is None

    @pytest.mark.asyncio
    async def test_get_all_stats(self, registry):
        """测试获取所有重试实例的统计信息."""
        await registry.get_or_create("retry1")
        await registry.get_or_create("retry2")

        stats = registry.get_all_stats()

        assert len(stats) == 2
        assert "retry1" in stats
        assert "retry2" in stats


class TestRetryDecorator:
    """测试重试装饰器."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """测试装饰器成功."""
        call_count = 0

        @retry("decorator_test", max_attempts=3, base_delay=0.1)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return f"success_{call_count}"

        result = await success_func()
        assert result == "success_1"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_retry(self):
        """测试装饰器重试."""
        call_count = 0

        @retry("decorator_retry_test", max_attempts=3, base_delay=0.1)
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ProviderError(f"失败 {call_count}", "test_provider")
            return f"success_{call_count}"

        result = await retry_func()
        assert result == "success_2"
        assert call_count == 2


class TestResilientExecutor:
    """测试弹性执行器."""

    @pytest.mark.asyncio
    async def test_resilient_execution_success(self):
        """测试弹性执行成功."""
        executor = ResilientExecutor(
            "test_circuit",
            "test_retry",
            circuit_config={"failure_threshold": 2, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 2, "base_delay": 0.1},
        )

        async def success_func():
            return "success"

        result = await executor.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_resilient_execution_with_retry_and_circuit_breaker(self):
        """测试带重试和熔断器的弹性执行."""
        call_count = 0

        async def sometimes_fail_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ProviderError(f"临时失败 {call_count}", "test_provider")
            return f"最终成功 {call_count}"

        executor = ResilientExecutor(
            "resilient_test",
            "resilient_retry",
            circuit_config={"failure_threshold": 3, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 3, "base_delay": 0.1},
        )

        result = await executor.execute(sometimes_fail_func)
        assert result == "最终成功 3"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_resilient_execution_with_circuit_breaker_open(self):
        """测试熔断器打开的弹性执行."""
        call_count = 0

        async def always_fail_func():
            nonlocal call_count
            call_count += 1
            raise ProviderError(f"总是失败 {call_count}", "test_provider")

        executor = ResilientExecutor(
            "circuit_test",
            "retry_test",
            circuit_config={"failure_threshold": 2, "recovery_timeout": 0.1},
            retry_config={"max_attempts": 2, "base_delay": 0.1},
        )

        # 第一次执行，触发熔断
        with pytest.raises(ProviderError):
            await executor.execute(always_fail_func)

        # 第二次执行，熔断器应该打开
        with pytest.raises(ProviderError):
            await executor.execute(always_fail_func)


class TestIntegration:
    """集成测试."""

    @pytest.mark.asyncio
    async def test_retry_with_different_providers(self):
        """测试不同提供商的重试."""
        registry = RetryRegistry()

        # 为不同提供商创建重试实例
        akshare_retry = await registry.get_or_create("akshare", RetryConfig(max_attempts=3, base_delay=0.1))
        yahoo_retry = await registry.get_or_create("yahoo", RetryConfig(max_attempts=2, base_delay=0.2))

        # 测试成功的akshare调用
        async def akshare_success():
            return "akshare数据"

        result = await akshare_retry.execute(akshare_success)
        assert result == "akshare数据"

        # 测试需要重试的yahoo调用
        call_count = 0

        async def yahoo_retry_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("第一次失败", "test_provider")
            return "yahoo数据"

        result = await yahoo_retry.execute(yahoo_retry_func)
        assert result == "yahoo数据"
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
