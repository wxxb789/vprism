"""数据提供商工厂类，用于创建和管理数据提供商实例."""

from typing import Any

from core.models.market import MarketType

from .akshare import AkShare
from .base import AuthConfig, AuthType, RateLimitConfig
from .yfinance import YFinance


class ProviderFactory:
    """数据提供商工厂类，用于创建各种数据提供商实例."""

    _providers: dict[str, Any] = {}

    @classmethod
    def create_yahoo_provider(
        cls, rate_limit: RateLimitConfig | None = None
    ) -> YFinance:
        """创建Yahoo Finance数据提供商.

        Args:
            rate_limit: 速率限制配置，如果为None则使用默认值

        Returns:
            YFinance实例
        """
        auth_config = AuthConfig(auth_type=AuthType.NONE, credentials={})

        rate_limit = rate_limit or RateLimitConfig(
            requests_per_minute=2000,
            requests_per_hour=10000,
            requests_per_day=100000,
            concurrent_requests=10,
            backoff_factor=1.5,
            max_retries=3,
            initial_delay=0.5,
        )

        return YFinance(auth_config, rate_limit)

    @classmethod
    def create_akshare_provider(
        cls, rate_limit: RateLimitConfig | None = None
    ) -> AkShare:
        """创建AkShare数据提供商.

        Args:
            rate_limit: 速率限制配置，如果为None则使用默认值

        Returns:
            AkShare实例
        """
        auth_config = AuthConfig(auth_type=AuthType.NONE, credentials={})

        rate_limit = rate_limit or RateLimitConfig(
            requests_per_minute=1000,
            requests_per_hour=5000,
            requests_per_day=20000,
            concurrent_requests=8,
            backoff_factor=2.0,
            max_retries=3,
            initial_delay=1.0,
        )

        return AkShare(auth_config, rate_limit)

    @classmethod
    def create_provider_by_market(
        cls, market: MarketType, api_key: str | None = None
    ) -> Any:
        """根据市场类型创建合适的提供商.

        Args:
            market: 市场类型
            api_key: API密钥（如需要）

        Returns:
            适合该市场的提供商实例
        """
        if market == MarketType.CN:
            # 中国市场使用AkShare（无需API密钥）
            return cls.create_akshare_provider()
        elif market == MarketType.US:
            # 美国市场使用Yahoo Finance
            return cls.create_yahoo_provider()
        elif market == MarketType.HK:
            # 香港市场使用AkShare
            return cls.create_akshare_provider()
        else:
            # 默认使用Yahoo Finance
            return cls.create_yahoo_provider()

    @classmethod
    def create_all_providers(cls) -> dict[str, Any]:
        """创建所有可用的提供商实例.

        Returns:
            包含所有提供商实例的字典
        """
        providers = {}

        # 创建Yahoo Finance提供商
        providers["yahoo"] = cls.create_yahoo_provider()

        # 创建AkShare提供商
        providers["akshare"] = cls.create_akshare_provider()

        return providers

    @classmethod
    def get_provider_by_name(cls, provider_name: str, **kwargs) -> Any:
        """根据名称获取提供商实例.

        Args:
            provider_name: 提供商名称
            **kwargs: 提供商特定参数

        Returns:
            提供商实例
        """
        provider_name = provider_name.lower()

        if provider_name == "yahoo":
            return cls.create_yahoo_provider(**kwargs)
        elif provider_name == "akshare":
            return cls.create_akshare_provider(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")


# 便捷函数
def get_provider(provider_name: str, **kwargs) -> Any:
    """根据名称获取提供商实例的便捷函数.

    Args:
        provider_name: 提供商名称
        **kwargs: 提供商特定参数

    Returns:
        提供商实例
    """
    return ProviderFactory.get_provider_by_name(provider_name, **kwargs)


def create_default_providers() -> dict[str, Any]:
    """创建默认的提供商集合.

    Returns:
        包含默认提供商的字典
    """
    return ProviderFactory.create_all_providers()
