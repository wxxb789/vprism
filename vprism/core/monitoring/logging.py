"""Logging utilities for monitoring and performance tracking."""

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any

from loguru import logger


def bind(**kwargs: Any) -> Any:
    """Bind context to logger."""
    return logger.bind(**kwargs)


class StructuredLogger:
    """Structured logger wrapper."""

    def __init__(self) -> None:
        self.logger = logger


class PerformanceLogger:
    """Performance logging decorator."""

    def __init__(self, operation: str):
        self.operation = operation

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    f"{self.operation} completed",
                    extra={
                        "operation": self.operation,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "success",
                    },
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"{self.operation} failed",
                    extra={
                        "operation": self.operation,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "error",
                        "error": str(e),
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    f"{self.operation} completed",
                    extra={
                        "operation": self.operation,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "success",
                    },
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"{self.operation} failed",
                    extra={
                        "operation": self.operation,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "error",
                        "error": str(e),
                    },
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
