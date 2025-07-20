"""
Core exception classes for vprism.

This module defines the exception hierarchy used throughout the platform,
providing structured error handling and debugging information.
"""

from typing import Any


class VPrismException(Exception):
    """
    Base exception class for all vprism errors.

    Provides structured error information including error codes,
    messages, and additional context for debugging.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Initialize VPrismException.

        Args:
            message: Human-readable error message
            error_code: Structured error code for programmatic handling
            details: Additional error context and debugging information
            cause: Original exception that caused this error
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


class ValidationException(VPrismException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)

        super().__init__(
            message=message, error_code="VALIDATION_ERROR", details=error_details
        )


class DataValidationException(ValidationException):
    """Raised when data or query validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            field=field,
            value=value,
            details=details,
        )


class ProviderException(VPrismException):
    """Base class for data provider related errors."""

    def __init__(
        self,
        message: str,
        provider: str,
        error_code: str = "PROVIDER_ERROR",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        error_details = details or {}
        error_details["provider"] = provider

        super().__init__(
            message=message, error_code=error_code, details=error_details, cause=cause
        )


class RateLimitException(ProviderException):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        provider: str,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if retry_after:
            error_details["retry_after_seconds"] = retry_after

        message = f"Rate limit exceeded for provider {provider}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"

        super().__init__(
            message=message,
            provider=provider,
            error_code="RATE_LIMIT_EXCEEDED",
            details=error_details,
        )


class AuthenticationException(ProviderException):
    """Raised when authentication with a provider fails."""

    def __init__(self, provider: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=f"Authentication failed for provider {provider}",
            provider=provider,
            error_code="AUTHENTICATION_FAILED",
            details=details,
        )


class DataNotFoundException(VPrismException):
    """Raised when requested data is not found."""

    def __init__(
        self,
        message: str = "Requested data not found",
        query: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query

        super().__init__(
            message=message, error_code="DATA_NOT_FOUND", details=error_details
        )


class ConfigurationException(VPrismException):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message, error_code="CONFIGURATION_ERROR", details=error_details
        )


class CacheException(VPrismException):
    """Raised when cache operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            details=error_details,
            cause=cause,
        )


class NetworkException(VPrismException):
    """Raised when network operations fail."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        error_details = details or {}
        if url:
            error_details["url"] = url
        if status_code:
            error_details["status_code"] = status_code

        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            details=error_details,
            cause=cause,
        )


class TimeoutException(VPrismException):
    """Raised when operations timeout."""

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message, error_code="TIMEOUT_ERROR", details=error_details
        )


class NoAvailableProviderException(VPrismException):
    """Raised when no suitable data provider is available."""

    def __init__(
        self,
        message: str = "No available data provider for request",
        query: str | None = None,
        attempted_providers: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query
        if attempted_providers:
            error_details["attempted_providers"] = attempted_providers

        super().__init__(
            message=message, error_code="NO_PROVIDER_AVAILABLE", details=error_details
        )
