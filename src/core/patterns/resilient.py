"""弹性执行器，结合熔断器和重试机制."""

from collections.abc import Awaitable, Callable
from typing import Any

from .circuitbreaker import CircuitBreakerConfig, circuit_breaker_registry
from .retry import ExponentialBackoffRetry, RetryConfig


class ResilientExecutor:
    """弹性执行器，结合熔断器和重试机制."""

    def __init__(
        self,
        circuit_breaker_name: str,
        retry_name: str,
        circuit_config: dict[str, Any] | None = None,
        retry_config: dict[str, Any] | None = None,
    ):
        self.circuit_breaker_name = circuit_breaker_name
        self.retry_name = retry_name
        self.circuit_config = circuit_config or {}
        self.retry_config = retry_config or {}

    async def execute(self, func: Callable[..., Awaitable], *args, **kwargs) -> Any:
        """执行函数，应用熔断器和重试机制.

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回结果
        """
        # 获取或创建熔断器
        circuit_config = CircuitBreakerConfig(name=self.circuit_breaker_name, **self.circuit_config)
        breaker = await circuit_breaker_registry.get_or_create(self.circuit_breaker_name, circuit_config)

        # 获取或创建重试器
        retry_config = RetryConfig(**self.retry_config)
        retry_instance = ExponentialBackoffRetry(retry_config)

        # 定义重试函数
        async def retry_func(*f_args, **f_kwargs):
            return await retry_instance.execute(func, *f_args, **f_kwargs)

        # 使用熔断器包装重试函数
        return await breaker.call(retry_func, *args, **kwargs)
