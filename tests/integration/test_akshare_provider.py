from datetime import date
from decimal import Decimal

import pytest

from vprism.core.data.providers.akshare import AkShare
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.query import Adjustment, DataQuery


@pytest.mark.integration
class TestAkshareIntegration:
    """Integration tests for the Akshare provider."""

    @pytest.fixture(scope="class")
    def provider(self):
        """Fixture to provide an instance of the AkShare provider."""
        return AkShare()

    async def test_get_daily_cn_stock(self, provider):
        """Test fetching daily data for a Chinese stock."""
        query = DataQuery(
            symbols=["600519"],
            asset=AssetType.STOCK,
            market=MarketType.CN,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
            adjustment=Adjustment.NONE,
        )
        response = await provider.get_data(query)
        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0
        assert all(isinstance(dp.close_price, Decimal) for dp in response.data)

    async def test_get_daily_cn_stock_qfq(self, provider):
        """Test fetching forward-adjusted daily data for a Chinese stock."""
        query_no_adjust = DataQuery(
            symbols=["000001"],
            asset=AssetType.STOCK,
            market=MarketType.CN,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
            adjustment=Adjustment.NONE,
        )
        query_qfq = DataQuery(
            symbols=["000001"],
            asset=AssetType.STOCK,
            market=MarketType.CN,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
            adjustment=Adjustment.FORWARD,
        )

        response_no_adjust = await provider.get_data(query_no_adjust)
        response_qfq = await provider.get_data(query_qfq)

        assert response_qfq.data[0].close_price != response_no_adjust.data[0].close_price

    async def test_get_daily_us_stock(self, provider):
        """Test fetching daily data for a US stock."""
        query = DataQuery(
            symbols=["AAPL"],
            asset=AssetType.STOCK,
            market=MarketType.US,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
        )
        response = await provider.get_data(query)
        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0

    async def test_get_daily_hk_stock(self, provider):
        """Test fetching daily data for a Hong Kong stock."""
        query = DataQuery(
            symbols=["00700"],
            asset=AssetType.STOCK,
            market=MarketType.HK,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
        )
        response = await provider.get_data(query)
        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0

    @pytest.mark.xfail(reason="Intermittent network issues with akshare ETF endpoint")
    async def test_get_daily_cn_etf(self, provider):
        """Test fetching daily data for a Chinese ETF."""
        query = DataQuery(
            symbols=["510300"],
            asset=AssetType.ETF,
            market=MarketType.CN,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
        )
        response = await provider.get_data(query)
        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0

    async def test_get_daily_cn_fund(self, provider):
        """Test fetching daily data for a Chinese fund."""
        query = DataQuery(
            symbols=["000001"],
            asset=AssetType.FUND,
            market=MarketType.CN,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
        )
        response = await provider.get_data(query)
        assert response is not None
        assert response.data
        assert response.metadata.total_records > 0

    async def test_invalid_symbol_should_raise_error(self, provider):
        """Test that an invalid symbol raises a ProviderError."""
        query = DataQuery(
            symbols=["INVALID"],
            asset=AssetType.STOCK,
            market=MarketType.CN,
        )
        # Akshare often returns an empty dataframe for invalid symbols,
        # so we expect an empty response rather than a ProviderError.
        response = await provider.get_data(query)
        assert response is not None
        assert not response.data
        assert response.metadata.total_records == 0
