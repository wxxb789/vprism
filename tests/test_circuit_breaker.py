"""测试熔断器实现."""

import asyncio

import pytest

from vprism.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
)
from vprism.core.exceptions import ProviderError


class TestCircuitBreakerConfig:
    """测试熔断器配置."""

    def test_default_config(self):
        """测试默认配置."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 3
        assert config.expected_exception == ProviderError
        assert config.name == "default"

    def test_custom_config(self):
        """测试自定义配置."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            half_open_max_calls=2,
            name="test_breaker",
        )

        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 2
        assert config.name == "test_breaker"


class TestCircuitBreaker:
    """测试熔断器."""

    @pytest.fixture
    def breaker(self):
        """创建熔断器实例."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 短超时用于测试
            half_open_max_calls=2,
            name="test_breaker",
        )
        return CircuitBreaker(config)

    @pytest.mark.asyncio
    async def test_initial_state(self, breaker):
        """测试初始状态."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """测试成功调用."""

        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_threshold(self, breaker):
        """测试失败阈值."""

        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        # 第一次失败
        with pytest.raises(ProviderError):
            await breaker.call(failure_func)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1

        # 第二次失败，应该触发熔断
        with pytest.raises(ProviderError):
            await breaker.call(failure_func)
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_open(self, breaker):
        """测试熔断器打开状态."""

        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        # 触发熔断
        for _ in range(2):
            try:
                await breaker.call(failure_func)
            except ProviderError:
                pass

        # 熔断器应该处于OPEN状态
        assert breaker.state == CircuitState.OPEN

        # 尝试调用应该被阻止
        async def any_func():
            return "should not reach here"

        with pytest.raises(ProviderError) as exc_info:
            await breaker.call(any_func)

        assert "熔断器处于OPEN状态" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_half_open_recovery(self, breaker):
        """测试半开状态恢复."""

        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        async def success_func():
            return "success"

        # 触发熔断
        for _ in range(2):
            try:
                await breaker.call(failure_func)
            except ProviderError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 等待超时
        await asyncio.sleep(0.2)

        # 第一次成功调用，应该转为HALF_OPEN
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 1

        # 第二次成功调用，应该转为CLOSED
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure(self, breaker):
        """测试半开状态失败."""

        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        # 触发熔断
        for _ in range(2):
            try:
                await breaker.call(failure_func)
            except ProviderError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 等待超时
        await asyncio.sleep(0.2)

        # 半开状态下失败，应该转回OPEN
        with pytest.raises(ProviderError):
            await breaker.call(failure_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_reset(self, breaker):
        """测试手动重置."""

        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        # 触发熔断
        for _ in range(2):
            try:
                await breaker.call(failure_func)
            except ProviderError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 手动重置
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_get_state(self, breaker):
        """测试获取状态."""
        state = breaker.get_state()

        assert state["name"] == "test_breaker"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["success_count"] == 0
        assert state["last_failure_time"] is None


class TestCircuitBreakerRegistry:
    """测试熔断器注册表."""

    @pytest.fixture
    def registry(self):
        """创建注册表实例."""
        return CircuitBreakerRegistry()

    @pytest.mark.asyncio
    async def test_get_or_create(self, registry):
        """测试获取或创建熔断器."""
        breaker1 = await registry.get_or_create("test_breaker")
        breaker2 = await registry.get_or_create("test_breaker")

        assert breaker1 is breaker2
        assert breaker1.config.name == "test_breaker"

    @pytest.mark.asyncio
    async def test_get_or_create_with_config(self, registry):
        """测试获取或创建带配置的熔断器."""
        config = CircuitBreakerConfig(failure_threshold=3, name="custom")
        breaker = await registry.get_or_create("custom_breaker", config)

        assert breaker.config.failure_threshold == 3
        assert breaker.config.name == "custom"

    def test_get_breaker(self, registry):
        """测试获取指定熔断器."""
        assert registry.get_breaker("non_existent") is None

    @pytest.mark.asyncio
    async def test_get_all_states(self, registry):
        """测试获取所有熔断器状态."""
        await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")

        states = registry.get_all_states()

        assert len(states) == 2
        assert "breaker1" in states
        assert "breaker2" in states

    @pytest.mark.asyncio
    async def test_reset_all(self, registry):
        """测试重置所有熔断器."""
        breaker = await registry.get_or_create("test_breaker")

        # 模拟失败状态
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5

        await registry.reset_all()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestCircuitBreakerDecorator:
    """测试熔断器装饰器."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """测试装饰器成功."""

        @circuit_breaker(
            "decorator_test",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=2,
        )
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_failure(self):
        """测试装饰器失败."""

        @circuit_breaker(
            "decorator_failure_test",
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=2,
        )
        async def failure_func():
            raise ProviderError("测试失败", "test_provider")

        # 第一次失败
        with pytest.raises(ProviderError):
            await failure_func()

        # 第二次调用应该被熔断
        with pytest.raises(ProviderError) as exc_info:
            await failure_func()

        assert "熔断器处于OPEN状态" in str(exc_info.value)


class TestIntegration:
    """集成测试."""

    @pytest.mark.asyncio
    async def test_multiple_providers_with_circuit_breakers(self):
        """测试多个提供商使用熔断器."""
        registry = CircuitBreakerRegistry()

        # 为不同提供商创建熔断器
        akshare_breaker = await registry.get_or_create(
            "akshare", CircuitBreakerConfig(failure_threshold=3, name="akshare")
        )
        yahoo_breaker = await registry.get_or_create(
            "yahoo", CircuitBreakerConfig(failure_threshold=2, name="yahoo")
        )

        async def akshare_call():
            raise ProviderError("akshare失败", "akshare")

        async def yahoo_call():
            return "yahoo数据"

        # 触发akshare熔断
        for _ in range(3):
            try:
                await akshare_breaker.call(akshare_call)
            except ProviderError:
                pass

        # akshare应该被熔断
        assert akshare_breaker.state == CircuitState.OPEN
        assert yahoo_breaker.state == CircuitState.CLOSED

        # yahoo应该正常工作
        result = await yahoo_breaker.call(yahoo_call)
        assert result == "yahoo数据"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
