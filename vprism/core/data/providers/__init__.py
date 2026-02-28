"""Data provider adapter framework."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vprism.core.data.providers.base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from vprism.core.data.providers.factory import (
    create_default_providers,
    create_provider,
)
from vprism.core.data.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from vprism.core.data.providers.akshare import AkShare
    from vprism.core.data.providers.alpha_vantage import AlphaVantage
    from vprism.core.data.providers.yfinance import YFinance

__all__ = [
    "DataProvider",
    "ProviderCapability",
    "RateLimitConfig",
    "AuthConfig",
    "AuthType",
    "ProviderRegistry",
    "create_provider",
    "create_default_providers",
    "YFinance",
    "AkShare",
    "AlphaVantage",
]


def __getattr__(name: str) -> type:
    """Lazy-load concrete provider classes on first access."""
    if name == "YFinance":
        from vprism.core.data.providers.yfinance import YFinance

        return YFinance
    if name == "AkShare":
        from vprism.core.data.providers.akshare import AkShare

        return AkShare
    if name == "AlphaVantage":
        from vprism.core.data.providers.alpha_vantage import AlphaVantage

        return AlphaVantage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
