"""熔断器实现，用于处理提供商故障."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..exceptions import ProviderError


class CircuitState(Enum):
    """熔断器状态."""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


@dataclass
class CircuitBreakerConfig:
    """熔断器配置."""

    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 60.0  # 恢复超时时间(秒)
    half_open_max_calls: int = 3  # 半开状态最大调用次数
    expected_exception: type = ProviderError  # 预期异常类型
    name: str = "default"  # 熔断器名称


class CircuitBreaker:
    """熔断器实现."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.success_count = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Awaitable], *args, **kwargs) -> Any:
        """调用函数，应用熔断器逻辑.

        Args:
            func: 要调用的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回结果

        Raises:
            ProviderError: 当熔断器处于OPEN状态或调用失败时
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise ProviderError(
                        f"熔断器处于OPEN状态，{self.config.name}暂时不可用",
                        provider_name=self.config.name,
                        error_code="CIRCUIT_BREAKER_OPEN",
                        details={"remaining_time": self._get_remaining_time()},
                    )

            try:
                result = await func(*args, **kwargs)
                await self._on_success()
                return result

            except Exception as e:
                await self._on_failure(e)
                raise

    async def _on_success(self) -> None:
        """处理成功调用."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    async def _on_failure(self, exception: Exception) -> None:
        """处理失败调用."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器."""
        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    def _get_remaining_time(self) -> float:
        """获取剩余等待时间."""
        if self.last_failure_time is None:
            return 0.0

        remaining = self.config.recovery_timeout - (time.time() - self.last_failure_time)
        return max(0.0, remaining)

    def get_state(self) -> dict[str, Any]:
        """获取熔断器状态信息."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "remaining_time": self._get_remaining_time() if self.state == CircuitState.OPEN else 0.0,
        }

    def reset(self) -> None:
        """手动重置熔断器."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class CircuitBreakerRegistry:
    """熔断器注册表."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
        """获取或创建熔断器.

        Args:
            name: 熔断器名称
            config: 熔断器配置

        Returns:
            CircuitBreaker实例
        """
        async with self._lock:
            if name not in self._breakers:
                if config is None:
                    config = CircuitBreakerConfig(name=name)
                self._breakers[name] = CircuitBreaker(config)

            return self._breakers[name]

    def get_breaker(self, name: str) -> CircuitBreaker | None:
        """获取指定熔断器.

        Args:
            name: 熔断器名称

        Returns:
            CircuitBreaker实例或None
        """
        return self._breakers.get(name)

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """获取所有熔断器状态.

        Returns:
            熔断器状态字典
        """
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}

    async def reset_all(self) -> None:
        """重置所有熔断器."""
        async with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


# 全局熔断器注册表
circuit_breaker_registry = CircuitBreakerRegistry()


class CircuitBreakerDecorator:
    """熔断器装饰器."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig(name=name)

    def __call__(self, func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        """装饰器实现."""

        async def wrapper(*args, **kwargs):
            breaker = await circuit_breaker_registry.get_or_create(self.name, self.config)
            return await breaker.call(func, *args, **kwargs)

        return wrapper


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 3,
) -> CircuitBreakerDecorator:
    """熔断器装饰器工厂函数.

    Args:
        name: 熔断器名称
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时时间(秒)
        half_open_max_calls: 半开状态最大调用次数

    Returns:
        熔断器装饰器
    """
    config = CircuitBreakerConfig(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        half_open_max_calls=half_open_max_calls,
    )
    return CircuitBreakerDecorator(name, config)


# 便捷函数
async def get_circuit_breaker(name: str) -> CircuitBreaker:
    """获取指定熔断器."""
    return await circuit_breaker_registry.get_or_create(name)


def get_circuit_breaker_state(name: str) -> dict[str, Any] | None:
    """获取熔断器状态."""
    breaker = circuit_breaker_registry.get_breaker(name)
    return breaker.get_state() if breaker else None


def get_all_circuit_breaker_states() -> dict[str, dict[str, Any]]:
    """获取所有熔断器状态."""
    return circuit_breaker_registry.get_all_states()
