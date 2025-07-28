"""数据提供商适配器框架."""

from .akshare import AkShare
from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from .factory import ProviderFactory, create_default_providers, get_provider
from .alpha_vantage import AlphaVantage
from .registry import ProviderRegistry
# from .vprism import VPrism  # vprism provider no longer exists
from .yfinance import YFinance

__all__ = [
    "DataProvider",
    "ProviderCapability",
    "RateLimitConfig",
    "AuthConfig",
    "AuthType",
    "ProviderRegistry",
    "ProviderFactory",
    "get_provider",
    "create_default_providers",
    "YFinance",
    "AkShare",
    # "VPrism",
    "AlphaVantage",
]
