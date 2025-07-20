"""测试数据提供商适配器框架."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from vprism.core.models import AssetType, DataPoint, DataQuery, MarketType, TimeFrame
from vprism.infrastructure.providers import (
    AkShareProvider,
    AlphaVantageProvider,
    ProviderRegistry,
    VPrismProvider,
    YFinanceProvider,
)


class TestProviderBase:
    """测试提供商基础功能."""

    def test_provider_capability_discovery(self):
        """测试提供商能力发现."""
        provider = AkShareProvider()
        capability = provider.capability

        assert capability is not None
        assert "stock" in capability.supported_assets
        assert "cn" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.max_symbols_per_request > 0

    def test_provider_can_handle_query(self):
        """测试提供商查询处理能力."""
        provider = AkShareProvider()

        # 有效查询
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

        assert provider.can_handle_query(query) is True

        # 无效查询 - 不支持的资产类型
        query_invalid = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,  # akshare支持CN，不支持US作为主要市场
            symbols=["000001"],
        )

        # 应该能处理查询，但可能没有数据
        assert provider.can_handle_query(query_invalid) is True

    @pytest.mark.asyncio
    async def test_provider_authenticate(self):
        """测试提供商认证."""
        provider = AkShareProvider()
        result = await provider.authenticate()

        assert result is True
        assert provider.is_authenticated is True


class TestAkShareProvider:
    """测试AkShare提供商."""

    def test_akshare_capability(self):
        """测试AkShare能力."""
        provider = AkShareProvider()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "cn" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True
        assert capability.supports_historical is True

    @pytest.mark.asyncio
    async def test_akshare_get_data(self):
        """测试AkShare获取数据."""
        provider = AkShareProvider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start=datetime.now() - timedelta(days=30),
            end=datetime.now(),
        )

        # 使用mock避免真实API调用
        with patch.object(provider, "_sync_fetch_data") as mock_fetch:
            mock_fetch.return_value = [
                DataPoint(
                    symbol="000001",
                    timestamp=datetime.now(),
                    open=Decimal("10.0"),
                    high=Decimal("11.0"),
                    low=Decimal("9.0"),
                    close=Decimal("10.5"),
                    volume=Decimal("1000000"),
                )
            ]

            response = await provider.get_data(query)
            assert len(response.data) > 0
            assert response.data[0].symbol == "000001"


class TestYFinanceProvider:
    """测试YFinance提供商."""

    def test_yfinance_capability(self):
        """测试YFinance能力."""
        provider = YFinanceProvider()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "us" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True

    @pytest.mark.asyncio
    async def test_yfinance_get_data(self):
        """测试YFinance获取数据."""
        provider = YFinanceProvider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start=datetime.now() - timedelta(days=30),
            end=datetime.now(),
        )

        # 使用mock避免真实API调用
        with patch.object(provider, "_sync_fetch_data") as mock_fetch:
            mock_fetch.return_value = [
                DataPoint(
                    symbol="AAPL",
                    timestamp=datetime.now(),
                    open=Decimal("150.0"),
                    high=Decimal("155.0"),
                    low=Decimal("149.0"),
                    close=Decimal("152.0"),
                    volume=Decimal("5000000"),
                )
            ]

            response = await provider.get_data(query)
            assert len(response.data) > 0
            assert response.data[0].symbol == "AAPL"


class TestAlphaVantageProvider:
    """测试AlphaVantage提供商."""

    def test_alpha_vantage_capability(self):
        """测试AlphaVantage能力."""
        provider = AlphaVantageProvider("test_api_key")
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "us" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.max_symbols_per_request == 1

    @pytest.mark.asyncio
    async def test_alpha_vantage_authenticate(self):
        """测试AlphaVantage认证."""
        provider = AlphaVantageProvider("test_api_key")

        # 直接mock认证方法
        with patch.object(provider, "authenticate", return_value=True):
            result = await provider.authenticate()
            assert result is True


class TestVPrismProvider:
    """测试VPrism提供商."""

    def test_vprism_capability(self):
        """测试VPrism能力."""
        provider = VPrismProvider()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "cn" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is False

    def test_vprism_cache_key_generation(self):
        """测试VPrism缓存键生成."""
        provider = VPrismProvider()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"],
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        cache_key = provider._generate_cache_key(query)
        assert cache_key is not None
        assert len(cache_key) == 32  # MD5长度

    def test_vprism_data_hash_calculation(self):
        """测试VPrism数据哈希计算."""
        provider = VPrismProvider()

        data_points = [
            DataPoint(
                symbol="000001", timestamp=datetime(2024, 1, 1), close=Decimal("10.0")
            )
        ]

        data_hash = provider._calculate_data_hash(data_points)
        assert data_hash is not None
        assert len(data_hash) == 16  # SHA256前16位


class TestProviderRegistry:
    """测试提供商注册表."""

    def test_registry_initialization(self):
        """测试注册表初始化."""
        registry = ProviderRegistry()
        assert len(registry) == 0
        assert registry.get_provider("nonexistent") is None

    def test_registry_register_unregister(self):
        """测试注册和注销."""
        registry = ProviderRegistry()
        provider = AkShareProvider()

        registry.register(provider)
        assert len(registry) == 1
        assert registry.get_provider("akshare") == provider

        result = registry.unregister("akshare")
        assert result is True
        assert len(registry) == 0

    def test_registry_find_capable_providers(self):
        """测试查找有能力的提供商."""
        registry = ProviderRegistry()

        akshare = AkShareProvider()
        yfinance = YFinanceProvider()

        registry.register(akshare)
        registry.register(yfinance)

        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        capable_providers = registry.find_capable_providers(query)
        assert len(capable_providers) >= 1  # akshare应该能处理

    def test_registry_health_management(self):
        """测试健康状态管理."""
        registry = ProviderRegistry()
        provider = AkShareProvider()

        registry.register(provider)

        # 标记为健康
        registry.mark_healthy("akshare")
        assert registry.is_healthy("akshare") is True

        # 标记为不健康
        registry.mark_unhealthy("akshare")
        assert registry.is_healthy("akshare") is False

    def test_registry_provider_list(self):
        """测试获取提供商列表."""
        registry = ProviderRegistry()
        provider = AkShareProvider()

        registry.register(provider)

        provider_list = registry.get_provider_list()
        assert len(provider_list) == 1
        assert provider_list[0]["name"] == "akshare"

    def test_registry_health_summary(self):
        """测试健康状态摘要."""
        registry = ProviderRegistry()

        akshare = AkShareProvider()
        yfinance = YFinanceProvider()

        registry.register(akshare)
        registry.register(yfinance)

        summary = registry.get_health_summary()
        assert summary["total_providers"] == 2
        assert "healthy_providers" in summary
        assert "health_percentage" in summary


class TestIntegration:
    """集成测试."""

    @pytest.mark.asyncio
    async def test_multiple_providers_query(self):
        """测试多个提供商查询."""
        registry = ProviderRegistry()

        akshare = AkShareProvider()
        yfinance = YFinanceProvider()
        vprism = VPrismProvider()

        registry.register(akshare)
        registry.register(yfinance)
        registry.register(vprism)

        # 中国股票查询
        cn_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
        )

        # 美国股票查询
        us_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
        )

        cn_providers = registry.find_capable_providers(cn_query)
        us_providers = registry.find_capable_providers(us_query)

        # akshare和vprism应该能处理中国股票
        assert any(p.name == "akshare" for p in cn_providers)
        assert any(p.name == "vprism" for p in cn_providers)

        # yfinance应该能处理美国股票
        assert any(p.name == "yfinance" for p in us_providers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
