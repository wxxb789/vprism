"""Logging utilities for monitoring and performance tracking."""

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast, overload

from vprism.core.logging.config import LogConfig

try:
    from loguru import Logger as _LoguruLogger
    from loguru import logger as _logger
except ImportError:

    class _LoguruLogger:  # type: ignore
        """A mock Loguru logger class."""

        def bind(self, **kwargs: Any) -> "Any":
            return self

        def info(self, message: str, **kwargs: Any) -> None:
            logging.info(message, **kwargs)

        def error(self, message: str, **kwargs: Any) -> None:
            logging.error(message, **kwargs)

        def warning(self, message: str, **kwargs: Any) -> None:
            logging.warning(message, **kwargs)

        def debug(self, message: str, **kwargs: Any) -> None:
            logging.debug(message, **kwargs)

    _logger = _LoguruLogger()


P = ParamSpec("P")
T = TypeVar("T")

# Define a union type for the logger to handle both loguru and standard logging
type AnyLogger = logging.Logger | _LoguruLogger
logger: AnyLogger = _logger
type LoguruLogger = _LoguruLogger


def bind(**kwargs: Any) -> AnyLogger:
    """Bind context to logger."""
    if hasattr(logger, "bind"):
        return logger.bind(**kwargs)
    return logger


def get_logger(name: str | None = None) -> AnyLogger:
    """Get logger instance."""
    if name:
        try:
            from loguru import logger as loguru_logger

            return loguru_logger.bind(name=name)
        except ImportError:
            return logging.getLogger(name)
    return logger


def configure_logging(level: str = "INFO", **kwargs: Any) -> None:
    """Configure logging."""
    try:
        from loguru import logger as loguru_logger

        # 创建配置对象
        config = LogConfig(level=level, **kwargs)

        # 移除默认处理器
        loguru_logger.remove()

        # 添加控制台处理器
        if config.console_output:
            import sys

            loguru_logger.add(
                sink=sys.stderr,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
                level=config.level,
                serialize=(config.format == "json"),
                colorize=config.colorize,
                backtrace=config.backtrace,
                diagnose=config.diagnose,
            )

        # 添加文件处理器
        if config.file_output and config.file_path:
            # 确保目录存在
            import os

            os.makedirs(os.path.dirname(config.file_path) or ".", exist_ok=True)

            loguru_logger.add(
                sink=config.file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
                level=config.level,
                serialize=(config.format == "json"),
                rotation=config.rotation,
                retention=config.retention,
                compression=config.compression,
                enqueue=config.enqueue,
                catch=config.catch,
            )
    except ImportError:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            **{k: v for k, v in kwargs.items() if k not in ["console_output", "file_output", "file_path"]},
        )


class StructuredLogger:
    """Structured logger wrapper."""

    def __init__(self, config: "LogConfig | None" = None) -> None:
        """Initialize structured logger."""

        self.config = config or LogConfig()
        self.logger: AnyLogger = get_logger()
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup logger with configuration."""
        try:
            import sys

            from loguru import logger as loguru_logger

            # Remove default handler
            loguru_logger.remove()

            # Add console handler
            if self.config.console_output:
                loguru_logger.add(
                    sink=sys.stderr,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
                    level=self.config.level,
                    serialize=(self.config.format == "json"),
                    colorize=self.config.colorize,
                    backtrace=self.config.backtrace,
                    diagnose=self.config.diagnose,
                )

            # Add file handler
            if self.config.file_output and self.config.file_path:
                loguru_logger.add(
                    sink=self.config.file_path,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
                    level=self.config.level,
                    serialize=(self.config.format == "json"),
                    rotation=self.config.rotation,
                    retention=self.config.retention,
                    compression=self.config.compression,
                    enqueue=self.config.enqueue,
                    catch=self.config.catch,
                )

            self.logger = loguru_logger
        except ImportError:
            pass

    def configure(self, **kwargs: Any) -> None:
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._setup_logger()

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        try:
            self.logger.info(message, **kwargs)
        except Exception:
            self.logger.info(f"{message} {kwargs}")

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        try:
            self.logger.error(message, **kwargs)
        except Exception:
            self.logger.error(f"{message} {kwargs}")

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        try:
            self.logger.warning(message, **kwargs)
        except Exception:
            self.logger.warning(f"{message} {kwargs}")

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        try:
            self.logger.debug(message, **kwargs)
        except Exception:
            self.logger.debug(f"{message} {kwargs}")


class PerformanceLogger:
    """Performance logging decorator."""

    def __init__(self, operation: str):
        """Initialize performance logger.

        Args:
            operation: Operation name for logging
        """
        self.operation = operation

    @overload
    def __call__(self, func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...

    @overload
    def __call__(self, func: Callable[P, T]) -> Callable[P, T]: ...

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        """Decorator function."""

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                bind(
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                    status="success",
                ).info(f"{self.operation} completed")
                return result
            except Exception as e:
                duration = time.time() - start_time
                bind(
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                    status="error",
                    error=str(e),
                ).error(f"{self.operation} failed")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            try:
                # We need to cast to Awaitable[T] here to satisfy mypy
                result = await cast("Awaitable[T]", func(*args, **kwargs))
                duration = time.time() - start_time
                bind(
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                    status="success",
                ).info(f"{self.operation} completed")
                return result
            except Exception as e:
                duration = time.time() - start_time
                bind(
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                    status="error",
                    error=str(e),
                ).error(f"{self.operation} failed")
                raise

        if asyncio.iscoroutinefunction(func):
            return cast("Callable[P, T]", async_wrapper)
        return wrapper


__all__ = [
    "logger",
    "LoguruLogger",
    "bind",
    "get_logger",
    "configure_logging",
    "StructuredLogger",
    "PerformanceLogger",
    "AnyLogger",
]
