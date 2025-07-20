"""数据提供商适配器框架."""

from .akshare_provider import AkShareProvider
from .alpha_vantage_provider import AlphaVantageProvider
from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from .registry import ProviderRegistry
from .vprism_provider import VPrismProvider
from .yfinance_provider import YFinanceProvider

__all__ = [
    "DataProvider",
    "ProviderCapability",
    "RateLimitConfig",
    "AuthConfig",
    "AuthType",
    "ProviderRegistry",
    "AkShareProvider",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "VPrismProvider",
]
