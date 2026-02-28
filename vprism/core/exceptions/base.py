"""vprism core exception hierarchy."""

from typing import Any


class VPrismError(Exception):
    """Base vprism exception."""

    def __init__(
        self,
        message: str,
        error_code: str = "GENERAL_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ProviderError(VPrismError):
    """Data provider exception."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        error_code: str = "PROVIDER_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, error_code, details)
        self.provider_name = provider_name


class DataValidationError(VPrismError):
    """Data validation exception."""

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


class AuthenticationError(ProviderError):
    """Authentication exception."""

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
    """Network exception."""

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


class RateLimitError(ProviderError):
    """Rate limit exception."""

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


class NoCapableProviderError(VPrismError):
    """No capable provider exception."""

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
    """All providers failed exception."""

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
    """Cache exception."""

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


class UnresolvedSymbolError(VPrismError):
    """Symbol could not be resolved to a canonical form."""

    def __init__(
        self,
        message: str,
        raw_symbol: str | None = None,
        market: str | None = None,
        asset_type: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super_details = details or {}
        if raw_symbol:
            super_details["raw_symbol"] = raw_symbol
        if market:
            super_details["market"] = market
        if asset_type:
            super_details["asset_type"] = asset_type
        super().__init__(message, "UNRESOLVED_SYMBOL", super_details)
