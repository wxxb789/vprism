"""错误处理和日志记录模块."""

import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from .base import VPrismError
from .codes import ErrorCode
from .messages import format_error_response


class ErrorHandler:
    """统一的错误处理器."""

    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self._configure_logging()

    def _configure_logging(self) -> None:
        """配置日志记录."""
        logger.remove()  # 移除默认处理器
        logger.add(
            "logs/vprism.log",
            rotation="10 MB",
            retention="30 days",
            level=self.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message} | {extra}",
            backtrace=True,
            diagnose=True,
        )

        # 控制台输出
        logger.add(
            lambda msg: print(msg, end=""),
            level=self.log_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> | {message}",
            colorize=True,
        )

    def log_error(
        self,
        error: Exception | VPrismError,
        context: dict[str, Any] | None = None,
        level: str = "ERROR",
    ) -> None:
        """记录错误日志.

        Args:
            error: 异常对象
            context: 上下文信息
            level: 日志级别
        """
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now(UTC).isoformat(),
            "stack_trace": traceback.format_exc(),
            **(context or {}),
        }

        if isinstance(error, VPrismError):
            error_context.update(
                {
                    "error_code": error.error_code,
                    "details": error.details,
                }
            )

        logger.opt(depth=2).log(
            level,
            "{error_message} | context={context}",
            error_message=str(error),
            context=error_context,
        )

    def create_error_response(
        self,
        error: Exception | VPrismError,
        error_code: ErrorCode | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """创建标准化的错误响应.

        Args:
            error: 异常对象
            error_code: 错误代码(如果error不是VPrismError)
            **kwargs: 额外的错误详情

        Returns:
            标准化的错误响应
        """
        if isinstance(error, VPrismError):
            return format_error_response(
                ErrorCode(error.error_code),
                message=error.message,
                **{**error.details, **kwargs},
            )
        else:
            # 对于非VPrismError异常
            error_code = error_code or ErrorCode.INTERNAL_ERROR
            return format_error_response(error_code, message=str(error), **kwargs)

    def handle_exception(
        self,
        error: Exception,
        operation: str,
        provider: str | None = None,
        **context: Any,
    ) -> VPrismError:
        """处理异常并返回标准化的VPrismError.

        Args:
            error: 原始异常
            operation: 操作名称
            provider: 提供商名称
            **context: 上下文信息

        Returns:
            标准化的VPrismError
        """
        error_context = {
            "operation": operation,
            "provider": provider,
            **context,
        }

        # 记录错误
        self.log_error(error, error_context)

        # 转换为标准错误
        if isinstance(error, VPrismError):
            return error

        # 根据异常类型映射到标准错误
        return self._map_to_standard_error(error, error_context)

    def _map_to_standard_error(self, error: Exception, context: dict[str, Any]) -> VPrismError:
        """将标准异常映射到VPrismError."""
        from .base import (
            CacheError,
            DataValidationError,
            NetworkError,
            ProviderError,
            VPrismError,
        )

        error_type = type(error).__name__
        provider = context.get("provider")

        # 根据异常类型进行映射
        if "Timeout" in error_type or "timeout" in str(error).lower():
            if provider:
                return ProviderError(
                    f"提供商{provider}请求超时",
                    provider_name=provider,
                    error_code="PROVIDER_TIMEOUT",
                    details=context,
                )
            else:
                return VPrismError(
                    "请求超时",
                    error_code="CONNECTION_TIMEOUT",
                    details=context,
                )

        elif "Connection" in error_type or "connection" in str(error).lower():
            if provider:
                return NetworkError(
                    f"无法连接到提供商{provider}",
                    provider_name=provider,
                    details=context,
                )
            else:
                return NetworkError(
                    "网络连接失败",
                    provider_name="unknown",
                    details=context,
                )

        elif "Validation" in error_type or "validation" in str(error).lower() or "数据格式无效" in str(error):
            return DataValidationError(
                str(error),
                validation_errors=context.get("validation_errors", {}),
                details=context,
            )

        elif "Cache" in error_type or "cache" in str(error).lower():
            return CacheError(
                str(error),
                cache_type=context.get("cache_type"),
                details=context,
            )

        else:
            # 默认映射为内部错误
            return VPrismError(
                str(error),
                error_code="INTERNAL_ERROR",
                details=context,
            )


class ErrorTracker:
    """错误追踪和统计."""

    def __init__(self):
        self.error_counts: dict[str, int] = {}
        self.last_errors: dict[str, dict[str, Any]] = {}

    def record_error(
        self,
        error_code: str,
        provider: str | None = None,
        operation: str | None = None,
    ) -> None:
        """记录错误统计."""
        key = f"{error_code}:{provider}:{operation}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1

        self.last_errors[key] = {
            "error_code": error_code,
            "provider": provider,
            "operation": operation,
            "timestamp": datetime.now(UTC).isoformat(),
            "count": self.error_counts[key],
        }

    def get_error_stats(self) -> dict[str, Any]:
        """获取错误统计信息."""
        return {
            "error_counts": self.error_counts,
            "last_errors": self.last_errors,
            "total_errors": sum(self.error_counts.values()),
        }


class ErrorContextManager:
    """错误上下文管理器."""

    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.operation = None
        self.provider = None
        self.context = {}

    def set_context(self, operation: str, provider: str | None = None, **context: Any) -> None:
        """设置错误上下文."""
        self.operation = operation
        self.provider = provider
        self.context = context

    @contextmanager
    def error_context(self, operation: str, provider: str | None = None, **context: Any):
        """错误上下文管理器."""
        self.set_context(operation, provider, **context)
        try:
            yield
        except Exception as e:
            raise self.error_handler.handle_exception(e, operation, provider, **context)

    def safe_execute(self, func, *args, **kwargs):
        """安全执行函数."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise self.error_handler.handle_exception(e, self.operation, self.provider, **self.context)


# 全局错误处理器实例
error_handler = ErrorHandler()
error_tracker = ErrorTracker()
error_context = ErrorContextManager(error_handler)


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器."""
    return error_handler


def get_error_tracker() -> ErrorTracker:
    """获取错误追踪器."""
    return error_tracker


def get_error_context() -> ErrorContextManager:
    """获取错误上下文管理器."""
    return error_context
