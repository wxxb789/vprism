"""数据提供商适配器框架."""

from .akshare_provider import AkShareProvider
from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from .factory import ProviderFactory, create_default_providers, get_provider
from .registry import ProviderRegistry
from .vprism_provider import VPrismProvider
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
    "VPrismProvider",
]
