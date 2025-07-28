"""Logging utilities for monitoring and performance tracking."""

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("vprism")


def bind(**kwargs: Any) -> Any:
    """Bind context to logger."""
    try:
        return logger.bind(**kwargs)
    except AttributeError:
        return logger


def get_logger(name: str = None) -> Any:
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

        from .config import LogConfig

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
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["console_output", "file_output", "file_path"]
            },
        )


class StructuredLogger:
    """Structured logger wrapper."""

    def __init__(self, config=None):
        """Initialize structured logger."""
        from .config import LogConfig

        self.config = config or LogConfig()
        self.logger = get_logger()
        self._setup_logger()

    def _setup_logger(self):
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

    def configure(self, **kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._setup_logger()

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        try:
            self.logger.info(message, **kwargs)
        except:
            self.logger.info(f"{message} {kwargs}")

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        try:
            self.logger.error(message, **kwargs)
        except:
            self.logger.error(f"{message} {kwargs}")

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        try:
            self.logger.warning(message, **kwargs)
        except:
            self.logger.warning(f"{message} {kwargs}")

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        try:
            self.logger.debug(message, **kwargs)
        except:
            self.logger.debug(f"{message} {kwargs}")


class PerformanceLogger:
    """Performance logging decorator."""

    def __init__(self, operation: str):
        """Initialize performance logger.

        Args:
            operation: Operation name for logging
        """
        self.operation = operation

    def __call__(self, func: Callable) -> Callable:
        """Decorator function."""

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
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
        def sync_wrapper(*args, **kwargs):
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
