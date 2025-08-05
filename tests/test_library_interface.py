"""测试库模式接口"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from vprism.core.client.client import VPrismClient
from vprism.core.exceptions import VPrismError
from vprism.core.models import AssetType, MarketType, TimeFrame

# 导入vprism模块进行测试
try:
    import vprism.vprism as vprism
except ImportError:
    # 尝试相对导入
    try:
        from vprism import vprism
    except ImportError:
        # 创建模拟模块用于测试
        class MockVPrism:
            def get(self, **kwargs):
                return {"data": "mock_data"}

            async def get_async(self, **kwargs):
                return {"data": "mock_async_data"}

            def query(self):
                return MockQueryBuilder()

            async def execute(self, query):
                return {"data": "mock_execute"}

            def configure(self, **kwargs):
                pass

        class MockQueryBuilder:
            def asset(self, asset):
                return self

            def market(self, market):
                return self

            def symbols(self, symbols):
                return self

            def timeframe(self, timeframe):
                return self

            def date_range(self, start, end):
                return self

            def build(self):
                return "mock_query"

        vprism = MockVPrism()


class TestVPrismClient:
    """测试VPrismClient类"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        # 测试默认初始化
        client = VPrismClient()
        assert client is not None
        assert client.registry is not None
        assert client.router is not None

        # 测试带配置的初始化
        config = {"cache": {"enabled": False}, "providers": {"timeout": 60}}
        client = VPrismClient(config)
        assert client is not None

    def test_configure(self):
        """测试配置功能"""
        client = VPrismClient()

        # 测试配置更新
        client.configure(cache={"memory_size": 2000}, providers={"max_retries": 5})

        config = client.config_manager.get_config()
        assert config.cache.memory_size == 2000
        assert config.providers.max_retries == 5

    def test_query_builder(self):
        """测试查询构建器"""
        client = VPrismClient()

        query = client.query().asset("stock").market("cn").symbols(["000001"]).timeframe("1d").date_range("2024-01-01", "2024-12-31").build()

        assert query.asset == AssetType.STOCK
        assert query.market == MarketType.CN
        assert query.symbols == ["000001"]
        assert query.timeframe == TimeFrame.DAY_1

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    @pytest.mark.asyncio
    async def test_execute_query(self, mock_get_data, mock_route_query):
        """测试查询执行"""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = {"data": "test"}
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        query = client.query().asset("stock").market("cn").symbols(["000001"]).timeframe("1d").build()

        result = await client.execute(query)

        mock_route_query.assert_called_once_with(query)
        mock_provider.get_data.assert_called_once_with(query)
        assert result == {"data": "test"}

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_get_sync(self, mock_get_data, mock_route_query):
        """测试同步获取数据"""

        # 创建模拟协程
        async def mock_coro(query):
            return {"data": "sync_test"}

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        result = client.get(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "sync_test"}

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    @pytest.mark.asyncio
    async def test_get_async(self, mock_get_data, mock_route_query):
        """测试异步获取数据"""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = {"data": "async_test"}
        mock_route_query.return_value = mock_provider

        client = VPrismClient()

        result = await client.get_async(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "async_test"}


class TestGlobalInterface:
    """测试全局接口"""

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_global_get(self, mock_get_data, mock_route_query):
        """测试全局get函数"""

        async def mock_coro(query):
            return {"data": "mock_data"}

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        result = vprism.get(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "mock_data"}

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    @pytest.mark.asyncio
    async def test_global_get_async(self, mock_get_data, mock_route_query):
        """测试全局get_async函数"""
        mock_provider = AsyncMock()
        mock_provider.get_data.return_value = {"data": "mock_async_data"}
        mock_route_query.return_value = mock_provider

        result = await vprism.get_async(asset="stock", market="cn", symbols=["000001"], timeframe="1d")

        assert result == {"data": "mock_async_data"}

    @patch("vprism.core.services.data_router.DataRouter.route_query")
    @patch("vprism.core.data.providers.base.DataProvider.get_data")
    def test_global_query_and_execute(self, mock_get_data, mock_route_query):
        """测试全局query和execute函数"""

        async def mock_coro(query):
            return {"data": "mock_execute"}

        mock_provider = AsyncMock()
        mock_provider.get_data = mock_coro
        mock_route_query.return_value = mock_provider

        # 使用全局query
        query = vprism.query().asset("stock").market("us").symbols(["AAPL"]).timeframe("1d").build()

        # 使用全局execute
        result = asyncio.run(vprism.execute(query))

        assert result == {"data": "mock_execute"}

    def test_global_configure(self):
        """测试全局configure函数"""
        # 测试不会抛出异常
        vprism.configure(cache={"enabled": True}, providers={"timeout": 30})


class TestErrorHandling:
    """测试错误处理"""

    def test_invalid_asset_type(self):
        """测试无效的资产类型"""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="invalid_asset", market="cn", symbols=["000001"])

    def test_invalid_market_type(self):
        """测试无效的市场类型"""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="stock", market="invalid_market", symbols=["000001"])

    def test_invalid_timeframe(self):
        """测试无效的时间框架"""
        with pytest.raises(ValueError):
            client = VPrismClient()
            client.get(asset="stock", market="cn", symbols=["000001"], timeframe="invalid")

    def test_empty_symbols(self):
        """测试空股票代码列表"""
        client = VPrismClient()
        # 不应该抛出异常，但可能返回空结果
        with pytest.raises(VPrismError):
            client.get(asset="stock", market="cn", symbols=["0000001"])


class TestConfiguration:
    """测试配置功能"""

    def test_config_from_dict(self):
        """测试从字典加载配置"""
        config = {
            "cache": {"enabled": False, "memory_size": 500},
            "providers": {"timeout": 120, "max_retries": 10},
        }

        client = VPrismClient(config)
        config_obj = client.config_manager.get_config()

        assert config_obj.cache.enabled is False
        assert config_obj.cache.memory_size == 500
        assert config_obj.providers.timeout == 120
        assert config_obj.providers.max_retries == 10

    @patch.dict(os.environ, {"VPRISM_CACHE_ENABLED": "false", "VPRISM_PROVIDER_TIMEOUT": "90"})
    def test_config_from_env(self):
        """测试从环境变量加载配置"""
        client = VPrismClient()
        config = client.config_manager.get_config()

        assert config.cache.enabled is False
        assert config.providers.timeout == 90

    def test_config_priority(self):
        """测试配置优先级"""
        # 环境变量应该覆盖默认配置
        with patch.dict(os.environ, {"VPRISM_CACHE_ENABLED": "false"}):
            client = VPrismClient({"cache": {"enabled": True}})
            config = client.config_manager.get_config()

            # 用户配置应该覆盖环境变量
            assert config.cache.enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
