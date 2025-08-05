"""vprism核心异常类."""

from typing import Any


class VPrismError(Exception):
    """vprism基础异常类."""

    def __init__(
        self,
        message: str,
        error_code: str = "GENERAL_ERROR",
        details: dict[str, Any] | None = None,
    ):
        """初始化异常.

        Args:
            message: 错误消息
            error_code: 错误代码
            details: 额外详情
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ProviderError(VPrismError):
    """数据提供商相关异常."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        error_code: str = "PROVIDER_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, error_code, details)
        self.provider_name = provider_name


class RateLimitError(ProviderError):
    """速率限制异常."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if retry_after is not None:
            super_details["retry_after"] = retry_after
        super().__init__(message, provider_name, "RATE_LIMIT_ERROR", super_details)
        self.retry_after = retry_after


class DataValidationError(VPrismError):
    """数据验证异常."""

    def __init__(
        self,
        message: str,
        validation_errors: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if validation_errors:
            super_details["validation_errors"] = validation_errors
        super().__init__(message, "VALIDATION_ERROR", super_details)
        self.validation_errors = validation_errors or {}


class NoCapableProviderError(VPrismError):
    """没有可用提供商异常."""

    def __init__(
        self,
        message: str,
        query_details: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if query_details:
            super_details["query"] = query_details
        super().__init__(message, "NO_PROVIDER_ERROR", super_details)


class NoAvailableProviderError(VPrismError):
    """所有提供商都失败异常."""

    def __init__(
        self,
        message: str,
        failed_providers: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if failed_providers:
            super_details["failed_providers"] = failed_providers
        super().__init__(message, "ALL_PROVIDERS_FAILED", super_details)


class CacheError(VPrismError):
    """缓存相关异常."""

    def __init__(
        self,
        message: str,
        cache_type: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if cache_type:
            super_details["cache_type"] = cache_type
        super().__init__(message, "CACHE_ERROR", super_details)


class AuthenticationError(ProviderError):
    """认证异常."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        auth_method: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if auth_method:
            super_details["auth_method"] = auth_method
        super().__init__(message, provider_name, "AUTHENTICATION_ERROR", super_details)


class NetworkError(ProviderError):
    """网络异常."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if status_code is not None:
            super_details["status_code"] = status_code
        super().__init__(message, provider_name, "NETWORK_ERROR", super_details)
