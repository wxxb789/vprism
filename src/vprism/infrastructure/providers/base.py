"""数据提供商抽象基类."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from vprism.core.models import DataPoint, DataQuery, DataResponse


class AuthType(str, Enum):
    """认证类型枚举."""

    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    NONE = "none"


@dataclass
class ProviderCapability:
    """提供商能力描述."""

    supported_assets: set[str]
    supported_markets: set[str]
    supported_timeframes: set[str]
    max_symbols_per_request: int
    supports_real_time: bool
    supports_historical: bool
    data_delay_seconds: int
    rate_limits: dict[str, int] = None


@dataclass
class RateLimitConfig:
    """速率限制配置."""

    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    concurrent_requests: int
    backoff_factor: float = 2.0
    max_retries: int = 3
    initial_delay: float = 1.0


@dataclass
class AuthConfig:
    """认证配置."""

    auth_type: AuthType
    credentials: dict[str, str]
    required_fields: list[str] = None


class DataProvider(ABC):
    """数据提供商抽象基类."""

    def __init__(self, name: str, auth_config: AuthConfig, rate_limit: RateLimitConfig):
        """初始化数据提供商.

        Args:
            name: 提供商名称
            auth_config: 认证配置
            rate_limit: 速率限制配置
        """
        self.name = name
        self.auth_config = auth_config
        self.rate_limit = rate_limit
        self._capability: ProviderCapability | None = None
        self._is_authenticated = False

    @property
    def capability(self) -> ProviderCapability:
        """获取提供商能力."""
        if self._capability is None:
            self._capability = self._discover_capability()
        return self._capability

    @abstractmethod
    def _discover_capability(self) -> ProviderCapability:
        """发现提供商能力.

        Returns:
            提供商能力描述
        """
        pass

    @abstractmethod
    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据.

        Args:
            query: 数据查询对象

        Returns:
            数据响应
        """
        pass

    @abstractmethod
    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据.

        Args:
            query: 数据查询对象

        Yields:
            单个数据点
        """
        pass

    def can_handle_query(self, query: DataQuery) -> bool:
        """检查提供商是否能处理查询.

        Args:
            query: 数据查询对象

        Returns:
            是否能处理该查询
        """
        cap = self.capability

        # 获取查询参数的值
        asset_value = str(query.asset.value) if query.asset else None
        market_value = str(query.market.value) if query.market else None
        timeframe_value = str(query.timeframe.value) if query.timeframe else None

        return not (
            (asset_value and asset_value not in cap.supported_assets)
            or (market_value and market_value not in cap.supported_markets)
            or (timeframe_value and timeframe_value not in cap.supported_timeframes)
            or (query.symbols and len(query.symbols) > cap.max_symbols_per_request)
        )

    @abstractmethod
    async def authenticate(self) -> bool:
        """与提供商进行身份验证.

        Returns:
            认证是否成功
        """
        pass

    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证."""
        return self._is_authenticated

    def validate_credentials(self) -> bool:
        """验证认证凭据是否完整.

        Returns:
            凭据是否有效
        """
        if self.auth_config.auth_type == AuthType.NONE:
            return True

        required_fields = self.auth_config.required_fields or []
        return all(field in self.auth_config.credentials for field in required_fields)

    def get_rate_limit_info(self) -> dict[str, int]:
        """获取速率限制信息.

        Returns:
            速率限制信息
        """
        return {
            "rpm": self.rate_limit.requests_per_minute,
            "rph": self.rate_limit.requests_per_hour,
            "rpd": self.rate_limit.requests_per_day,
            "concurrent": self.rate_limit.concurrent_requests,
        }

    async def health_check(self) -> bool:
        """健康检查.

        Returns:
            提供商是否健康
        """
        try:
            if not self.is_authenticated:
                await self.authenticate()

            # 执行简单的健康检查查询
            test_query = DataQuery(asset="stock", symbols=["TEST"], limit=1)

            if self.can_handle_query(test_query):
                result = await self.get_data(test_query)
                return result is not None
            else:
                return True  # 如果不能处理测试查询，认为健康

        except Exception:
            return False

    def __repr__(self) -> str:
        """字符串表示."""
        return f"{self.__class__.__name__}(name='{self.name}')"
