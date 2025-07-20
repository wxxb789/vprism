"""数据提供商适配器框架."""

from .akshare_provider import AkShareProvider
from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from .factory import ProviderFactory, get_provider, create_default_providers
from .registry import ProviderRegistry
from .yahoo_provider import YahooFinanceProvider

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
    "YahooFinanceProvider",
    "AkShareProvider",
]
