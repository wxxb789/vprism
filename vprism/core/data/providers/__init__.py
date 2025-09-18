"""数据提供商适配器框架."""

from vprism.core.data.providers.akshare import AkShare
from vprism.core.data.providers.alpha_vantage import AlphaVantage
from vprism.core.data.providers.base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from vprism.core.data.providers.factory import (
    ProviderFactory,
    create_default_providers,
    get_provider,
)
from vprism.core.data.providers.registry import ProviderRegistry

# from .vprism import VPrism  # vprism provider no longer exists
from vprism.core.data.providers.stub_provider import StubProviderRow, VPrismStubProvider
from vprism.core.data.providers.yfinance import YFinance

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
    "VPrismStubProvider",
    "StubProviderRow",
]
