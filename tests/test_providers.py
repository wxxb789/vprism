"""测试数据提供商适配器框架."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from core.data.providers import (
    AkShare,
    ProviderRegistry,
    # VPrism,  # vprism provider no longer exists
    YFinance,
)
from core.models import AssetType, DataPoint, DataQuery, MarketType, TimeFrame


class TestProviderBase:
    """测试提供商基础功能."""

    def test_provider_capability_discovery(self):
        """测试提供商能力发现."""
        provider = AkShare()
        capability = provider.capability

        assert capability is not None
        assert AssetType.STOCK in capability.supported_assets
        assert MarketType.CN in capability.supported_markets
        assert TimeFrame.DAY_1 in capability.supported_timeframes
        assert capability.max_symbols_per_request > 0

    def test_provider_can_handle_query(self):
        """测试提供商查询处理能力."""
        provider = AkShare()

        # 有效查询
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        assert provider.can_handle_query(query) is True

        # 测试不同市场
        us_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        assert provider.can_handle_query(us_query) is True

    @pytest.mark.asyncio
    async def test_provider_authenticate(self):
        """测试提供商认证."""
        provider = AkShare()
        result = await provider.authenticate()

        assert result is True
        assert provider.is_authenticated is True


class TestAkShare:
    """测试AkShare提供商."""

    def test_akshare_capability(self):
        """测试AkShare能力."""
        provider = AkShare()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "cn" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True
        assert capability.supports_historical is True

    @pytest.mark.asyncio
    async def test_akshare_get_data(self):
        """测试AkShare获取数据."""
        provider = AkShare()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        # 使用mock避免真实API调用
        with patch.object(provider, "_fetch_data") as mock_fetch:
            data_points = [
                DataPoint(
                    symbol="000001",
                    market=MarketType.CN,
                    timestamp=datetime.now(),
                    open_price=Decimal("10.0"),
                    high_price=Decimal("11.0"),
                    low_price=Decimal("9.0"),
                    close_price=Decimal("10.5"),
                    volume=Decimal("1000000"),
                    provider="akshare",
                )
            ]
            mock_response = Mock()
            mock_response.data = data_points
            mock_fetch.return_value = mock_response

            response = await provider.get_data(query)
            assert response.data is not None
            assert response.data[0].symbol == "000001"


class TestYFinance:
    """测试YFinance提供商."""

    def test_yfinance_capability(self):
        """测试YFinance能力."""
        provider = YFinance()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "us" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True

    @pytest.mark.asyncio
    async def test_yfinance_get_data(self):
        """测试YFinance获取数据."""
        provider = YFinance()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        # 使用mock避免真实API调用
        with patch.object(provider, "_get_historical_data") as mock_fetch:
            mock_response = Mock()
            mock_response.data = [
                DataPoint(
                    symbol="AAPL",
                    market=MarketType.US,
                    timestamp=datetime.now(),
                    open_price=Decimal("150.0"),
                    high_price=Decimal("155.0"),
                    low_price=Decimal("149.0"),
                    close_price=Decimal("152.0"),
                    volume=Decimal("5000000"),
                    provider="yfinance",
                )
            ]
            mock_fetch.return_value = mock_response

            response = await provider.get_data(query)
            assert response.data is not None
            assert response.data[0].symbol == "AAPL"


class TestIntegration:
    """集成测试."""

    @pytest.mark.asyncio
    async def test_multiple_providers_query(self):
        """测试多个提供商查询."""
        registry = ProviderRegistry()

        akshare = AkShare()
        yahoo = YFinance()

        registry.register(akshare)
        registry.register(yahoo)

        # 中国股票查询
        cn_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        # 美国股票查询
        us_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        cn_providers = registry.find_capable_providers(cn_query)
        us_providers = registry.find_capable_providers(us_query)

        # akshare应该能处理中国股票
        assert any(p.name == "akshare" for p in cn_providers)
        # yfinance应该能处理美国股票
        assert any(p.name == "yfinance" for p in us_providers)

    def test_registry_register_unregister(self):
        """测试注册和注销."""
        registry = ProviderRegistry()
        provider = AkShare()

        registry.register(provider)
        assert len(registry) == 1
        assert registry.get_provider("akshare") == provider

        result = registry.unregister("akshare")
        assert result is True
        assert len(registry) == 0

    def test_registry_find_capable_providers(self):
        """测试查找有能力的提供商."""
        registry = ProviderRegistry()

        akshare = AkShare()
        yfinance = YFinance()

        registry.register(akshare)
        registry.register(yfinance)

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"])

        capable_providers = registry.find_capable_providers(query)
        assert len(capable_providers) >= 1  # akshare应该能处理

    def test_registry_health_management(self):
        """测试健康状态管理."""
        registry = ProviderRegistry()
        provider = AkShare()

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
        provider = AkShare()

        registry.register(provider)

        provider_list = registry.get_provider_list()
        assert len(provider_list) == 1
        assert provider_list[0]["name"] == "akshare"

    def test_registry_health_summary(self):
        """测试健康状态摘要."""
        registry = ProviderRegistry()

        akshare = AkShare()
        yfinance = YFinance()

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

        akshare = AkShare()
        yfinance = YFinance()
        # vprism = VPrism()  # vprism provider no longer exists

        registry.register(akshare)
        registry.register(yfinance)
        # registry.register(vprism)  # vprism provider no longer exists

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

        # akshare应该能处理中国股票 (vprism provider no longer exists)
        assert any(p.name == "akshare" for p in cn_providers)
        # vprism provider no longer exists

        # yfinance应该能处理美国股票
        assert any(p.name == "yfinance" for p in us_providers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
