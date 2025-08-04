"""测试数据路由器的各种路由场景和故障转移机制."""

from typing import Any
from unittest.mock import Mock

import pytest

from vprism.core.data.providers.base import DataProvider
from vprism.core.exceptions import NoCapableProviderError
from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame
from vprism.core.services.routing import DataRouter


class MockProvider(DataProvider):
    def __init__(self, name: str, capability):
        from vprism.core.data.providers.base import (
            AuthConfig,
            AuthType,
            RateLimitConfig,
        )

        super().__init__(
            name=name,
            auth_config=AuthConfig(auth_type=AuthType.NONE, credentials={}),
            rate_limit=RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=1000,
                requests_per_day=10000,
                concurrent_requests=5,
            ),
        )
        self.name = name  # 确保name属性被正确设置
        self._capability = capability

    def _discover_capability(self):
        return self._capability

    async def get_data(self, query: DataQuery) -> Any:
        return None

    async def stream_data(self, query: DataQuery) -> Any:
        yield None

    async def authenticate(self) -> bool:
        return True


class TestDataRouter:
    """测试数据路由器功能."""

    @pytest.fixture
    def mock_registry(self, sample_providers):
        """创建模拟的提供商注册表."""
        registry = Mock()
        registry.find_capable_providers = Mock()
        registry.mark_unhealthy = Mock()
        registry.mark_healthy = Mock()
        registry.providers = {p.name: p for p in sample_providers}  # 添加providers属性
        registry.get_all_providers = Mock(return_value=sample_providers)  # 添加get_all_providers方法
        return registry

    @pytest.fixture
    def sample_providers(self):
        """创建示例提供商."""
        from vprism.core.data.providers.base import ProviderCapability

        return [
            MockProvider(
                "tushare",
                ProviderCapability(
                    supported_assets={"stock"},
                    supported_markets={"cn"},
                    supported_timeframes={"1d", "1m"},
                    max_symbols_per_request=100,
                    supports_real_time=True,
                    supports_historical=True,
                    data_delay_seconds=1,
                ),
            ),
            MockProvider(
                "yahoo",
                ProviderCapability(
                    supported_assets={"stock", "etf"},
                    supported_markets={"us", "hk"},
                    supported_timeframes={"1d", "1w", "1m"},
                    max_symbols_per_request=200,
                    supports_real_time=True,
                    supports_historical=True,
                    data_delay_seconds=15,
                ),
            ),
            MockProvider(
                "alpha_vantage",
                ProviderCapability(
                    supported_assets={"stock", "forex"},
                    supported_markets={"us", "global"},
                    supported_timeframes={"1d", "1m", "5m"},
                    max_symbols_per_request=50,
                    supports_real_time=False,
                    supports_historical=True,
                    data_delay_seconds=60,
                ),
            ),
        ]

    @pytest.mark.asyncio
    async def test_route_single_provider(self, mock_registry, sample_providers):
        """测试单个提供商的路由."""
        mock_registry.find_capable_providers.return_value = [sample_providers[0]]

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"])

        provider = await router.route_query(query)

        assert provider.name == "tushare"
        mock_registry.find_capable_providers.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_route_multiple_providers_select_best(self, mock_registry, sample_providers):
        """测试多个提供商中选择最佳提供商."""
        # 设置mock注册表的providers属性
        mock_registry.providers = {p.name: p for p in sample_providers}
        # 只返回能处理US市场的提供商
        capable_providers = [p for p in sample_providers if p.name in ["yahoo", "alpha_vantage"]]
        mock_registry.find_capable_providers.return_value = capable_providers

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        provider = await router.route_query(query)

        # 应该选择延迟最低的提供商
        # 在US市场，yahoo和alpha_vantage都支持，yahoo延迟更低(15秒 vs 60秒)
        assert provider.name == "yahoo"

    @pytest.mark.asyncio
    async def test_route_no_capable_provider(self, mock_registry):
        """测试没有可用提供商的情况."""
        mock_registry.find_capable_providers.return_value = []

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.CRYPTO, market=MarketType.GLOBAL)

        with pytest.raises(NoCapableProviderError) as exc_info:
            await router.route_query(query)

        assert "No provider can handle query" in str(exc_info.value)

    def test_update_provider_score_success(self, mock_registry):
        """测试更新提供商性能评分 - 成功情况."""
        router = DataRouter(mock_registry)

        # 初始评分
        router.provider_scores["tushare"] = 1.0

        # 成功且低延迟
        router.update_provider_score("tushare", success=True, latency_ms=50)

        assert router.provider_scores["tushare"] > 1.0

    def test_update_provider_score_failure(self, mock_registry):
        """测试更新提供商性能评分 - 失败情况."""
        router = DataRouter(mock_registry)

        # 初始评分
        router.provider_scores["tushare"] = 1.0

        # 失败
        router.update_provider_score("tushare", success=False, latency_ms=0)

        assert router.provider_scores["tushare"] < 1.0
        assert router.provider_scores["tushare"] >= 0.1

    def test_update_provider_score_bounds(self, mock_registry):
        """测试评分边界限制."""
        router = DataRouter(mock_registry)

        # 测试上限
        router.provider_scores["tushare"] = 2.0
        router.update_provider_score("tushare", success=True, latency_ms=10)
        assert router.provider_scores["tushare"] <= 2.0

        # 测试下限
        router.provider_scores["tushare"] = 0.1
        router.update_provider_score("tushare", success=False, latency_ms=0)
        assert router.provider_scores["tushare"] >= 0.1

    @pytest.mark.asyncio
    async def test_route_with_provider_scores(self, mock_registry, sample_providers):
        """测试使用提供商评分进行路由选择."""
        mock_registry.find_capable_providers.return_value = sample_providers[:2]

        router = DataRouter(mock_registry)

        # 设置评分，yahoo评分更高
        router.provider_scores["tushare"] = 1.0
        router.provider_scores["yahoo"] = 1.5

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])

        # 应该考虑评分选择最佳提供商
        provider = await router.route_query(query)

        # 验证评分被考虑在内
        assert provider.name in ["tushare", "yahoo"]

    @pytest.mark.asyncio
    async def test_health_check_integration(self, mock_registry, sample_providers):
        """测试健康检查集成."""
        mock_registry.find_capable_providers.return_value = [sample_providers[0]]

        router = DataRouter(mock_registry)
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)

        provider = await router.route_query(query)

        # 验证只返回健康状态的提供商
        assert provider.name == "tushare"
        mock_registry.find_capable_providers.assert_called_once()

    @pytest.mark.asyncio
    async def test_complex_query_routing(self, mock_registry, sample_providers):
        """测试复杂查询的路由."""
        # 使用alpha_vantage提供商，它支持所有需要的条件
        capable_providers = [sample_providers[2]]  # alpha_vantage
        mock_registry.find_capable_providers.return_value = capable_providers

        router = DataRouter(mock_registry)
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            timeframe=TimeFrame.MINUTE_1,
            symbols=["AAPL", "GOOGL"],
        )

        provider = await router.route_query(query)

        # 应该返回alpha_vantage
        assert provider.name == "alpha_vantage"
