"""Exception handling module."""

from vprism.core.exceptions.base import (
    AuthenticationError,
    CacheError,
    DataValidationError,
    DriftComputationError,
    NetworkError,
    NoAvailableProviderError,
    NoCapableProviderError,
    ProviderError,
    RateLimitError,
    VPrismError,
)
from vprism.core.exceptions.domain import DomainError
from vprism.core.exceptions.codes import ErrorCode
from vprism.core.exceptions.handler import (
    ErrorContextManager,
    ErrorHandler,
    ErrorTracker,
    error_context,
    error_handler,
    error_tracker,
)
from vprism.core.exceptions.messages import ErrorMessageTemplate, format_error_response

__all__ = [
    "VPrismError",
    "ProviderError",
    "RateLimitError",
    "DomainError",
    "DataValidationError",
    "DriftComputationError",
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
