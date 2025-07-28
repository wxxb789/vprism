"""Exception handling module."""

from .base import (
    AuthenticationError,
    CacheError,
    DataValidationError,
    NetworkError,
    NoAvailableProviderError,
    NoCapableProviderError,
    ProviderError,
    RateLimitError,
    VPrismError,
)
from .codes import ErrorCode
from .handler import (
    ErrorContextManager,
    ErrorHandler,
    ErrorTracker,
    error_context,
    error_handler,
    error_tracker,
)
from .messages import ErrorMessageTemplate, format_error_response

__all__ = [
    "VPrismError",
    "ProviderError",
    "RateLimitError",
    "DataValidationError",
    "NetworkError",
    "CacheError",
    "AuthenticationError",
    "NoCapableProviderError",
    "NoAvailableProviderError",
    "ErrorCode",
    "ErrorMessageTemplate",
    "format_error_response",
    "ErrorHandler",
    "ErrorTracker",
    "ErrorContextManager",
    "error_handler",
    "error_tracker",
    "error_context",
]
