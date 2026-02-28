"""Exception handling module."""

from vprism.core.exceptions.base import (
    AuthenticationError,
    CacheError,
    DataValidationError,
    NetworkError,
    NoAvailableProviderError,
    NoCapableProviderError,
    ProviderError,
    RateLimitError,
    UnresolvedSymbolError,
    VPrismError,
)
from vprism.core.exceptions.codes import ErrorCode
from vprism.core.exceptions.domain import DomainError

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
    "UnresolvedSymbolError",
    "DomainError",
    "ErrorCode",
]
