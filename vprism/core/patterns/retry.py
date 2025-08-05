"""重试机制实现，包括指数退避重试."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from vprism.core.exceptions import ProviderError, RateLimitError

T = TypeVar("T")


class RetryState(Enum):
    """重试状态."""

    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RetryConfig:
    """重试配置."""

    max_attempts: int = 3  # 最大重试次数
    base_delay: float = 1.0  # 基础延迟时间(秒)
    max_delay: float = 60.0  # 最大延迟时间(秒)
    multiplier: float = 2.0  # 延迟倍数
    jitter: bool = True  # 是否添加随机抖动
    exponential_base: float = 2.0  # 指数基数
    retry_on_exceptions: list[type] = field(default_factory=lambda: [ProviderError])
    skip_on_exceptions: list[type] = field(default_factory=lambda: [RateLimitError])


class ExponentialBackoffRetry:
    """指数退避重试实现."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt_count = 0
        self.total_delay = 0.0
        self.state = RetryState.READY
        self.last_exception: Exception | None = None

    async def execute(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """执行函数，应用重试逻辑.

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回结果

        Raises:
            Exception: 当所有重试都失败时抛出最后的异常
        """
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

                # 检查是否应该跳过重试
                if any(isinstance(e, exc_type) for exc_type in self.config.skip_on_exceptions):
                    self.state = RetryState.FAILED
                    raise e

                # 检查是否应该重试
                should_retry = any(isinstance(e, exc_type) for exc_type in self.config.retry_on_exceptions)

                if not should_retry or self.attempt_count >= self.config.max_attempts:
                    self.state = RetryState.FAILED
                    raise e

                # 计算延迟时间
                delay = self._calculate_delay(self.attempt_count - 1)

                # 等待重试
                await asyncio.sleep(delay)
                self.total_delay += delay

        # 如果循环完成但没有成功，则引发最后的异常
        if self.last_exception:
            raise self.last_exception
        # 这是一个备用，以防循环在没有异常的情况下退出
        raise RuntimeError("Retry loop completed without success or exception.")

    def _calculate_delay(self, attempt_number: int) -> float:
        """计算延迟时间.

        Args:
            attempt_number: 重试次数(从0开始)

        Returns:
            延迟时间(秒)
        """
        if attempt_number < 0:
            return 0.0

        # 指数退避计算
        delay = self.config.base_delay * (self.config.exponential_base**attempt_number)

        # 添加随机抖动
        if self.config.jitter:
            jitter_range = min(delay * 0.1, 1.0)  # 最多10%的抖动
            delay += random.uniform(-jitter_range, jitter_range)

        # 限制最大延迟
        return min(delay, self.config.max_delay)

    def get_stats(self) -> dict[str, Any]:
        """获取重试统计信息.

        Returns:
            重试统计字典
        """
        return {
            "attempts": self.attempt_count,
            "max_attempts": self.config.max_attempts,
            "total_delay": self.total_delay,
            "state": self.state.value,
            "last_exception": str(self.last_exception) if self.last_exception else None,
        }

    def reset(self) -> None:
        """重置重试状态."""
        self.attempt_count = 0
        self.total_delay = 0.0
        self.state = RetryState.READY
        self.last_exception = None


class RetryRegistry:
    """重试注册表."""

    def __init__(self) -> None:
        self._retries: dict[str, ExponentialBackoffRetry] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, name: str, config: RetryConfig | None = None) -> ExponentialBackoffRetry:
        """获取或创建重试实例.

        Args:
            name: 重试实例名称
            config: 重试配置

        Returns:
            ExponentialBackoffRetry实例
        """
        async with self._lock:
            if name not in self._retries:
                if config is None:
                    config = RetryConfig()
                self._retries[name] = ExponentialBackoffRetry(config)

            return self._retries[name]

    def get_retry(self, name: str) -> ExponentialBackoffRetry | None:
        """获取指定重试实例.

        Args:
            name: 重试实例名称

        Returns:
            ExponentialBackoffRetry实例或None
        """
        return self._retries.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有重试实例的统计信息.

        Returns:
            重试统计字典
        """
        return {name: retry.get_stats() for name, retry in self._retries.items()}


class RetryDecorator:
    """重试装饰器."""

    def __init__(self, name: str, config: RetryConfig | None = None):
        self.name = name
        self.config = config or RetryConfig()

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """装饰器实现."""

        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retry = ExponentialBackoffRetry(self.config)
            return await retry.execute(func, *args, **kwargs)

        return wrapper


# 全局重试注册表
retry_registry = RetryRegistry()


def retry(
    name: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
) -> RetryDecorator:
    """重试装饰器工厂函数.

    Args:
        name: 重试实例名称
        max_attempts: 最大重试次数
        base_delay: 基础延迟时间(秒)
        max_delay: 最大延迟时间(秒)
        multiplier: 延迟倍数

    Returns:
        RetryDecorator实例
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        multiplier=multiplier,
    )
    return RetryDecorator(name, config)


# 便捷函数
async def get_retry_instance(name: str) -> ExponentialBackoffRetry:
    """获取指定重试实例."""
    return await retry_registry.get_or_create(name)


def get_retry_stats(name: str) -> dict[str, Any] | None:
    """获取重试统计信息."""
    retry = retry_registry.get_retry(name)
    return retry.get_stats() if retry else None


def get_all_retry_stats() -> dict[str, dict[str, Any]]:
    """获取所有重试实例的统计信息."""
    return retry_registry.get_all_stats()


# 集成类：结合熔断器和重试机制
class ResilientExecutor:
    """弹性执行器，结合熔断器和重试机制."""

    def __init__(
        self,
        circuit_breaker_name: str,
        retry_name: str,
        circuit_config: dict[str, Any] | None = None,
        retry_config: dict[str, Any] | None = None,
    ) -> None:
        self.circuit_breaker_name = circuit_breaker_name
        self.retry_name = retry_name
        self.circuit_config = circuit_config or {}
        self.retry_config = retry_config or {}

    async def execute(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """执行函数，应用熔断器和重试机制.

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回结果
        """
        from vprism.core.patterns.circuitbreaker import (
            CircuitBreakerConfig,
            circuit_breaker_registry,
        )

        # 获取或创建熔断器
        circuit_config = CircuitBreakerConfig(name=self.circuit_breaker_name, **self.circuit_config)
        breaker = await circuit_breaker_registry.get_or_create(self.circuit_breaker_name, circuit_config)

        # 获取或创建重试器
        retry_config = RetryConfig(**self.retry_config)
        retry_instance = ExponentialBackoffRetry(retry_config)

        # 定义重试函数
        async def retry_func(*f_args: Any, **f_kwargs: Any) -> T:
            return await retry_instance.execute(func, *f_args, **f_kwargs)

        # 使用熔断器包装重试函数
        return await breaker.call(retry_func, *args, **kwargs)
