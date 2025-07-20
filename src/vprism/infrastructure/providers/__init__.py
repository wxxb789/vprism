"""数据提供商适配器框架."""

from .base import DataProvider, ProviderCapability, RateLimitConfig, AuthConfig, AuthType
from .registry import ProviderRegistry
from .akshare_provider import AkShareProvider
from .yfinance_provider import YFinanceProvider
from .alpha_vantage_provider import AlphaVantageProvider
from .vprism_provider import VPrismProvider

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
    "VPrismProvider"
]