"""Test data provider adapter framework."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from vprism.core.data.providers import (
    AkShare,
    ProviderRegistry,
    YFinance,
)
from vprism.core.models import AssetType, DataPoint, DataQuery, MarketType, TimeFrame


class TestProviderBase:
    """Test provider base functionality."""

    def test_provider_can_handle_query(self):
        """Test provider query handling capability."""
        provider = AkShare()

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        assert provider.can_handle_query(query) is True

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
        """Test provider authentication."""
        provider = AkShare()

        with patch.object(provider, "_initialize_akshare", return_value=None), patch.object(provider, "_ak", create=True) as ak_mock:

            class _DF:
                empty = False

            ak_mock.stock_zh_a_spot_em.return_value = _DF()
            result = await provider.authenticate()

        assert result is True
        assert provider.is_authenticated is True


class TestAkShare:
    """Test AkShare provider."""

    def test_akshare_capability(self):
        """Test AkShare capability discovery."""
        provider = AkShare()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "cn" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True
        assert capability.supports_historical is True

    @pytest.mark.asyncio
    async def test_akshare_get_data(self):
        """Test AkShare data retrieval with mocked akshare module."""
        provider = AkShare()

        with patch.object(provider, "authenticate", return_value=True), patch.object(provider, "_initialize_akshare", return_value=None):

            class _AkStub:
                def stock_zh_a_hist(self, **kwargs):
                    import pandas as pd

                    return pd.DataFrame(
                        {
                            "date": [datetime(2024, 1, 2)],
                            "open": [10.0],
                            "high": [11.0],
                            "low": [9.0],
                            "close": [10.5],
                            "volume": [1000],
                        }
                    )

                def stock_us_daily(self, **kwargs):
                    raise AssertionError("Should not be called in this test")

                def stock_hk_daily(self, **kwargs):
                    raise AssertionError("Should not be called in this test")

            provider._ak = _AkStub()
            provider._initialized = True
            provider._is_authenticated = True
            query = DataQuery(
                asset=AssetType.STOCK,
                market=MarketType.CN,
                symbols=["000001"],
                timeframe=TimeFrame.DAY_1,
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 2),
            )
            response = await provider.get_data(query)
            assert response is not None
            assert len(response.data) == 1
            dp = response.data[0]
            assert dp.symbol == "000001"
            assert dp.close_price == Decimal("10.5")


class TestYFinance:
    """Test YFinance provider."""

    def test_yfinance_capability(self):
        """Test YFinance capability discovery."""
        provider = YFinance()
        capability = provider.capability

        assert "stock" in capability.supported_assets
        assert "us" in capability.supported_markets
        assert "1d" in capability.supported_timeframes
        assert capability.supports_real_time is True

    @pytest.mark.asyncio
    async def test_yfinance_get_data(self):
        """Test YFinance data retrieval with mocked fetch."""
        provider = YFinance()
        if not provider._is_authenticated:
            pytest.skip("yfinance package not installed")

        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

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


class TestProviderRegistry:
    """Test provider registry operations."""

    @pytest.mark.asyncio
    async def test_multiple_providers_query(self):
        """Test registry returns correct providers for different markets."""
        registry = ProviderRegistry()

        akshare = AkShare()
        yahoo = YFinance()

        registry.register(akshare)
        registry.register(yahoo)

        cn_query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

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

        assert any(p.name == "akshare" for p in cn_providers)
        assert any(p.name == "yfinance" for p in us_providers)

    def test_register_unregister(self):
        """Test provider registration and unregistration."""
        registry = ProviderRegistry()
        provider = AkShare()

        registry.register(provider)
        assert len(registry) == 1
        assert registry.get_provider("akshare") == provider

        result = registry.unregister("akshare")
        assert result is True
        assert len(registry) == 0

    def test_health_management(self):
        """Test health status marking."""
        registry = ProviderRegistry()
        provider = AkShare()

        registry.register(provider)

        registry.mark_healthy("akshare")
        assert registry.is_healthy("akshare") is True

        registry.mark_unhealthy("akshare")
        assert registry.is_healthy("akshare") is False

    def test_provider_list(self):
        """Test provider list retrieval."""
        registry = ProviderRegistry()
        provider = AkShare()

        registry.register(provider)

        provider_list = registry.get_provider_list()
        assert len(provider_list) == 1
        assert provider_list[0]["name"] == "akshare"

    def test_health_summary(self):
        """Test health summary aggregation."""
        registry = ProviderRegistry()

        akshare = AkShare()
        yfinance = YFinance()

        registry.register(akshare)
        registry.register(yfinance)

        summary = registry.get_health_summary()
        assert summary["total_providers"] == 2
        assert "healthy_providers" in summary
        assert "health_percentage" in summary
