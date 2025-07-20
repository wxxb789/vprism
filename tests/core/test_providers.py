"""
Tests for data provider implementations.

This module contains comprehensive tests for all data provider implementations
including akshare, yfinance, and Alpha Vantage providers.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pandas as pd

from vprism.core.models import (
    AssetType,
    DataQuery,
    MarketType,
    TimeFrame,
)
from vprism.core.exceptions import ProviderException


class TestAkshareProvider:
    """Test suite for AkshareProvider."""

    @pytest.fixture
    def mock_akshare(self):
        """Mock akshare module."""
        with patch("vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.akshare_provider.ak", create=True
            ) as mock_ak:
                # Mock version
                mock_ak.__version__ = "1.12.0"

                # Mock stock spot data for health check
                mock_spot_df = pd.DataFrame(
                    {
                        "代码": ["000001", "000002"],
                        "名称": ["平安银行", "万科A"],
                        "最新价": [10.5, 20.3],
                    }
                )
                mock_ak.stock_zh_a_spot_em.return_value = mock_spot_df

                # Mock historical data
                mock_hist_df = pd.DataFrame(
                    {
                        "日期": ["2024-01-01", "2024-01-02"],
                        "开盘": [10.0, 10.2],
                        "最高": [10.5, 10.7],
                        "最低": [9.8, 10.0],
                        "收盘": [10.2, 10.5],
                        "成交量": [1000000, 1200000],
                        "成交额": [10200000, 12600000],
                    }
                )
                mock_ak.stock_zh_a_hist.return_value = mock_hist_df

                yield mock_ak

    @pytest.fixture
    def akshare_provider(self, mock_akshare):
        """Create AkshareProvider instance."""
        from vprism.core.providers.akshare_provider import AkshareProvider

        return AkshareProvider()

    def test_provider_initialization(self, akshare_provider):
        """Test provider initialization."""
        assert akshare_provider.name == "akshare"
        assert akshare_provider.auth_config.auth_type.value == "none"
        assert akshare_provider.rate_limit.requests_per_minute == 30

    def test_capability_discovery(self, akshare_provider):
        """Test provider capability discovery."""
        capability = akshare_provider.capability

        assert AssetType.STOCK in capability.supported_assets
        assert AssetType.BOND in capability.supported_assets
        assert MarketType.CN in capability.supported_markets
        assert TimeFrame.DAY_1 in capability.supported_timeframes
        assert capability.max_symbols_per_request == 1
        assert not capability.supports_real_time
        assert capability.supports_historical
        assert capability.data_delay_seconds == 900

    @pytest.mark.asyncio
    async def test_health_check_success(self, akshare_provider, mock_akshare):
        """Test successful health check."""
        result = await akshare_provider.health_check()
        assert result is True
        mock_akshare.stock_zh_a_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, akshare_provider, mock_akshare):
        """Test failed health check."""
        mock_akshare.stock_zh_a_spot_em.side_effect = Exception("Connection error")

        result = await akshare_provider.health_check()
        assert result is False

    def test_can_handle_query(self, akshare_provider):
        """Test query handling capability."""
        # Supported query
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )
        assert akshare_provider.can_handle_query(query) is True

        # Unsupported market
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.US, symbols=["AAPL"])
        assert akshare_provider.can_handle_query(query) is False

    @pytest.mark.asyncio
    async def test_get_data_success(self, akshare_provider, mock_akshare):
        """Test successful data retrieval."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        response = await akshare_provider.get_data(query)

        assert response is not None
        assert len(response.data) == 2  # Mock data has 2 rows
        assert response.source.name == "akshare"
        assert response.metadata.record_count == 2

        # Check data point structure
        data_point = response.data[0]
        assert data_point.symbol == "000001"
        assert isinstance(data_point.open, Decimal)
        assert isinstance(data_point.close, Decimal)

    @pytest.mark.asyncio
    async def test_get_data_unsupported_query(self, akshare_provider):
        """Test data retrieval with unsupported query."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,  # Unsupported market
            symbols=["AAPL"],
        )

        with pytest.raises(ProviderException) as exc_info:
            await akshare_provider.get_data(query)

        assert exc_info.value.error_code == "UNSUPPORTED_QUERY"

    @pytest.mark.asyncio
    async def test_stream_data_not_supported(self, akshare_provider):
        """Test that streaming is not supported."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["000001"])

        with pytest.raises(ProviderException) as exc_info:
            await akshare_provider.stream_data(query)

        assert exc_info.value.error_code == "STREAMING_NOT_SUPPORTED"

    def test_timeframe_mapping(self, akshare_provider):
        """Test timeframe mapping to akshare parameters."""
        assert akshare_provider._map_timeframe_to_akshare(TimeFrame.MINUTE_1) == "1"
        assert akshare_provider._map_timeframe_to_akshare(TimeFrame.MINUTE_5) == "5"
        assert akshare_provider._map_timeframe_to_akshare(TimeFrame.DAY_1) == "daily"
        assert akshare_provider._map_timeframe_to_akshare(TimeFrame.WEEK_1) == "weekly"

    def test_dataframe_standardization(self, akshare_provider):
        """Test DataFrame standardization."""
        # Create test DataFrame with Chinese column names
        df = pd.DataFrame(
            {
                "日期": ["2024-01-01", "2024-01-02"],
                "开盘": [10.0, 10.2],
                "最高": [10.5, 10.7],
                "最低": [9.8, 10.0],
                "收盘": [10.2, 10.5],
                "成交量": [1000000, 1200000],
                "成交额": [10200000, 12600000],
            }
        )

        data_points = akshare_provider._standardize_dataframe(df, "000001")

        assert len(data_points) == 2
        assert data_points[0].symbol == "000001"
        assert data_points[0].open == Decimal("10.0")
        assert data_points[0].close == Decimal("10.2")
        assert data_points[0].volume == Decimal("1000000")


class TestYfinanceProvider:
    """Test suite for YfinanceProvider."""

    @pytest.fixture
    def mock_yfinance(self):
        """Mock yfinance module."""
        with patch("vprism.core.providers.yfinance_provider.YFINANCE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.yfinance_provider.yf", create=True
            ) as mock_yf:
                # Mock version
                mock_yf.__version__ = "0.2.0"

                # Mock ticker for health check
                mock_ticker = Mock()
                mock_ticker.info = {"symbol": "AAPL", "longName": "Apple Inc."}
                mock_yf.Ticker.return_value = mock_ticker

                # Mock historical data
                mock_hist_df = pd.DataFrame(
                    {
                        "Open": [150.0, 151.0],
                        "High": [155.0, 156.0],
                        "Low": [149.0, 150.0],
                        "Close": [152.0, 153.0],
                        "Volume": [1000000, 1100000],
                        "Adj Close": [152.0, 153.0],
                    },
                    index=pd.date_range("2024-01-01", periods=2, freq="D"),
                )

                mock_ticker.history.return_value = mock_hist_df

                yield mock_yf

    @pytest.fixture
    def yfinance_provider(self, mock_yfinance):
        """Create YfinanceProvider instance."""
        from vprism.core.providers.yfinance_provider import YfinanceProvider

        return YfinanceProvider()

    def test_provider_initialization(self, yfinance_provider):
        """Test provider initialization."""
        assert yfinance_provider.name == "yfinance"
        assert yfinance_provider.auth_config.auth_type.value == "none"
        assert yfinance_provider.rate_limit.requests_per_minute == 60

    def test_capability_discovery(self, yfinance_provider):
        """Test provider capability discovery."""
        capability = yfinance_provider.capability

        assert AssetType.STOCK in capability.supported_assets
        assert AssetType.ETF in capability.supported_assets
        assert AssetType.CRYPTO in capability.supported_assets
        assert MarketType.US in capability.supported_markets
        assert MarketType.GLOBAL in capability.supported_markets
        assert TimeFrame.MINUTE_1 in capability.supported_timeframes
        assert capability.max_symbols_per_request == 100
        assert capability.supports_real_time
        assert capability.supports_historical

    @pytest.mark.asyncio
    async def test_health_check_success(self, yfinance_provider, mock_yfinance):
        """Test successful health check."""
        result = await yfinance_provider.health_check()
        assert result is True
        mock_yfinance.Ticker.assert_called_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_data_success(self, yfinance_provider, mock_yfinance):
        """Test successful data retrieval."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,
            symbols=["AAPL"],
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        response = await yfinance_provider.get_data(query)

        assert response is not None
        assert len(response.data) == 2  # Mock data has 2 rows
        assert response.source.name == "yfinance"
        assert response.metadata.record_count == 2

        # Check data point structure
        data_point = response.data[0]
        assert data_point.symbol == "AAPL"
        assert isinstance(data_point.open, Decimal)
        assert data_point.extra_fields.get("adj_close") is not None

    def test_timeframe_mapping(self, yfinance_provider):
        """Test timeframe mapping to yfinance parameters."""
        assert yfinance_provider._map_timeframe_to_yfinance(TimeFrame.MINUTE_1) == "1m"
        assert yfinance_provider._map_timeframe_to_yfinance(TimeFrame.MINUTE_5) == "5m"
        assert yfinance_provider._map_timeframe_to_yfinance(TimeFrame.DAY_1) == "1d"
        assert yfinance_provider._map_timeframe_to_yfinance(TimeFrame.WEEK_1) == "1wk"

    def test_get_asset_info(self, yfinance_provider, mock_yfinance):
        """Test asset information retrieval."""
        mock_ticker = Mock()
        mock_ticker.info = {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "currency": "USD",
            "exchange": "NASDAQ",
        }
        mock_yfinance.Ticker.return_value = mock_ticker

        info = yfinance_provider.get_asset_info("AAPL")

        assert info["symbol"] == "AAPL"
        assert info["name"] == "Apple Inc."
        assert info["sector"] == "Technology"
        assert info["currency"] == "USD"


class TestAlphaVantageProvider:
    """Test suite for AlphaVantageProvider."""

    @pytest.fixture
    def alpha_vantage_provider(self):
        """Create AlphaVantageProvider instance."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        return AlphaVantageProvider(api_key="test_api_key")

    def test_provider_initialization(self, alpha_vantage_provider):
        """Test provider initialization."""
        assert alpha_vantage_provider.name == "alpha_vantage"
        assert alpha_vantage_provider.auth_config.auth_type.value == "api_key"
        assert alpha_vantage_provider.rate_limit.requests_per_minute == 5
        assert alpha_vantage_provider.api_key == "test_api_key"

    def test_initialization_without_api_key(self):
        """Test initialization without API key raises error."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        with pytest.raises(ProviderException) as exc_info:
            AlphaVantageProvider(api_key="")

        assert exc_info.value.error_code == "MISSING_API_KEY"

    def test_capability_discovery(self, alpha_vantage_provider):
        """Test provider capability discovery."""
        capability = alpha_vantage_provider.capability

        assert AssetType.STOCK in capability.supported_assets
        assert AssetType.FOREX in capability.supported_assets
        assert AssetType.CRYPTO in capability.supported_assets
        assert MarketType.US in capability.supported_markets
        assert MarketType.GLOBAL in capability.supported_markets
        assert TimeFrame.MINUTE_1 in capability.supported_timeframes
        assert capability.max_symbols_per_request == 1
        assert capability.supports_real_time
        assert capability.supports_historical

    def test_build_request_params_stock(self, alpha_vantage_provider):
        """Test request parameter building for stocks."""
        query = DataQuery(
            asset=AssetType.STOCK, symbols=["AAPL"], timeframe=TimeFrame.DAY_1
        )

        params = alpha_vantage_provider._build_request_params(query)

        assert params["apikey"] == "test_api_key"
        assert params["function"] == "TIME_SERIES_DAILY"
        assert params["symbol"] == "AAPL"
        assert params["outputsize"] == "compact"

    def test_build_request_params_intraday(self, alpha_vantage_provider):
        """Test request parameter building for intraday data."""
        query = DataQuery(
            asset=AssetType.STOCK, symbols=["AAPL"], timeframe=TimeFrame.MINUTE_5
        )

        params = alpha_vantage_provider._build_request_params(query)

        assert params["function"] == "TIME_SERIES_INTRADAY"
        assert params["interval"] == "5min"

    def test_build_request_params_forex(self, alpha_vantage_provider):
        """Test request parameter building for forex."""
        query = DataQuery(
            asset=AssetType.FOREX, symbols=["EURUSD"], timeframe=TimeFrame.DAY_1
        )

        params = alpha_vantage_provider._build_request_params(query)

        assert params["function"] == "FX_DAILY"
        assert params["from_symbol"] == "EUR"
        assert params["to_symbol"] == "USD"

    def test_timeframe_mapping(self, alpha_vantage_provider):
        """Test timeframe mapping to Alpha Vantage parameters."""
        assert (
            alpha_vantage_provider._map_timeframe_to_alpha_vantage(TimeFrame.MINUTE_1)
            == "1min"
        )
        assert (
            alpha_vantage_provider._map_timeframe_to_alpha_vantage(TimeFrame.MINUTE_5)
            == "5min"
        )
        assert (
            alpha_vantage_provider._map_timeframe_to_alpha_vantage(TimeFrame.HOUR_1)
            == "60min"
        )

    @pytest.mark.asyncio
    async def test_parse_response_stock_success(self, alpha_vantage_provider):
        """Test successful stock response parsing."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-01": {
                    "1. open": "150.00",
                    "2. high": "155.00",
                    "3. low": "149.00",
                    "4. close": "152.00",
                    "5. volume": "1000000",
                },
                "2024-01-02": {
                    "1. open": "152.00",
                    "2. high": "156.00",
                    "3. low": "151.00",
                    "4. close": "154.00",
                    "5. volume": "1100000",
                },
            }
        }

        query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])

        data_points = await alpha_vantage_provider._parse_response(mock_response, query)

        assert len(data_points) == 2
        assert data_points[0].symbol == "AAPL"
        assert data_points[0].open == Decimal("150.00")
        assert data_points[0].close == Decimal("152.00")
        assert data_points[0].volume == Decimal("1000000")

    @pytest.mark.asyncio
    async def test_parse_response_api_error(self, alpha_vantage_provider):
        """Test response parsing with API error."""
        mock_response = Mock()
        mock_response.json.return_value = {"Error Message": "Invalid API call"}

        query = DataQuery(asset=AssetType.STOCK, symbols=["INVALID"])

        with pytest.raises(ProviderException) as exc_info:
            await alpha_vantage_provider._parse_response(mock_response, query)

        assert exc_info.value.error_code == "API_ERROR"

    @pytest.mark.asyncio
    async def test_parse_response_rate_limit(self, alpha_vantage_provider):
        """Test response parsing with rate limit error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute"
        }

        query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])

        with pytest.raises(ProviderException) as exc_info:
            await alpha_vantage_provider._parse_response(mock_response, query)

        assert exc_info.value.error_code == "RATE_LIMIT_EXCEEDED"

    def test_date_range_filtering(self, alpha_vantage_provider):
        """Test date range filtering."""
        from vprism.core.models import DataPoint

        data_points = [
            DataPoint(
                symbol="AAPL", timestamp=datetime(2024, 1, 1), close=Decimal("150.00")
            ),
            DataPoint(
                symbol="AAPL", timestamp=datetime(2024, 1, 15), close=Decimal("155.00")
            ),
            DataPoint(
                symbol="AAPL", timestamp=datetime(2024, 2, 1), close=Decimal("160.00")
            ),
        ]

        # Filter to January only
        filtered = alpha_vantage_provider._filter_by_date_range(
            data_points, start=datetime(2024, 1, 1), end=datetime(2024, 1, 31)
        )

        assert len(filtered) == 2
        assert all(point.timestamp.month == 1 for point in filtered)


class TestProviderIntegration:
    """Integration tests for provider functionality."""

    @pytest.mark.asyncio
    async def test_provider_registry_integration(self):
        """Test provider registration and discovery."""
        from vprism.core.provider_abstraction import EnhancedProviderRegistry
        from vprism.core.providers.akshare_provider import AkshareProvider

        registry = EnhancedProviderRegistry()

        # Mock akshare availability
        with patch("vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True):
            with patch("vprism.core.providers.akshare_provider.ak", create=True):
                provider = AkshareProvider()
                registry.register_provider(provider)

                # Test provider discovery
                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                capable_providers = registry.find_capable_providers(query)
                assert len(capable_providers) == 1
                assert capable_providers[0].name == "akshare"

    @pytest.mark.asyncio
    async def test_provider_error_handling(self):
        """Test provider error handling."""
        from vprism.core.providers.yfinance_provider import YfinanceProvider

        with patch("vprism.core.providers.yfinance_provider.YFINANCE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.yfinance_provider.yf", create=True
            ) as mock_yf:
                # Mock yfinance to raise an exception
                mock_ticker = Mock()
                mock_ticker.history.side_effect = Exception("Network error")
                mock_yf.Ticker.return_value = mock_ticker

                provider = YfinanceProvider()
                query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])

                with pytest.raises(ProviderException) as exc_info:
                    await provider.get_data(query)

                assert exc_info.value.error_code == "FETCH_ERROR"

    def test_provider_configuration_validation(self):
        """Test provider configuration validation."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        # Valid configuration
        provider = AlphaVantageProvider(api_key="valid_key")
        assert provider.auth_config.is_valid()

        # Invalid configuration should raise error during initialization
        with pytest.raises(ProviderException):
            AlphaVantageProvider(api_key="")


class TestProviderAdditionalFeatures:
    """Test additional provider features and edge cases."""

    @pytest.mark.asyncio
    async def test_akshare_additional_asset_types(self):
        """Test akshare provider with additional asset types."""
        with patch("vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.akshare_provider.ak", create=True
            ) as mock_ak:
                from vprism.core.providers.akshare_provider import AkshareProvider

                # Mock bond data
                mock_bond_df = pd.DataFrame(
                    {"日期": ["2024-01-01"], "开盘": [100.0], "收盘": [101.0]}
                )
                mock_ak.bond_zh_hs_cov_daily.return_value = mock_bond_df

                provider = AkshareProvider()

                # Test bond query
                query = DataQuery(
                    asset=AssetType.BOND, market=MarketType.CN, symbols=["123456"]
                )

                response = await provider.get_data(query)
                assert response is not None
                assert len(response.data) == 1

    @pytest.mark.asyncio
    async def test_akshare_fetch_error_handling(self):
        """Test akshare provider error handling in fetch."""
        with patch("vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.akshare_provider.ak", create=True
            ) as mock_ak:
                from vprism.core.providers.akshare_provider import AkshareProvider

                # Mock akshare to raise exception
                mock_ak.stock_zh_a_hist.side_effect = Exception("Network error")
                # Also mock the spot data for health check
                mock_ak.stock_zh_a_spot_em.return_value = pd.DataFrame(
                    {"代码": ["000001"]}
                )

                provider = AkshareProvider()
                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                # The provider should return a response with warnings, not raise an exception
                # because it continues processing other symbols
                response = await provider.get_data(query)
                assert response is not None
                assert len(response.data) == 0  # No data due to error
                assert len(response.metadata.warnings) > 0  # Should have warnings

    def test_akshare_get_stock_list(self):
        """Test akshare stock list functionality."""
        with patch("vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.akshare_provider.ak", create=True
            ) as mock_ak:
                from vprism.core.providers.akshare_provider import AkshareProvider

                # Mock stock list data
                mock_stock_df = pd.DataFrame(
                    {
                        "代码": ["000001", "000002"],
                        "名称": ["平安银行", "万科A"],
                        "最新价": [10.5, 20.3],
                    }
                )
                mock_ak.stock_zh_a_spot_em.return_value = mock_stock_df

                provider = AkshareProvider()
                stock_list = provider.get_stock_list("A")

                assert len(stock_list) == 2
                assert stock_list[0]["symbol"] == "000001"
                assert stock_list[0]["name"] == "平安银行"

    @pytest.mark.asyncio
    async def test_yfinance_batch_download_fallback(self):
        """Test yfinance batch download with fallback."""
        with patch("vprism.core.providers.yfinance_provider.YFINANCE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.yfinance_provider.yf", create=True
            ) as mock_yf:
                from vprism.core.providers.yfinance_provider import YfinanceProvider

                # Mock batch download to fail
                mock_yf.download.side_effect = Exception("Batch failed")

                # Mock individual ticker success
                mock_ticker = Mock()
                mock_hist_df = pd.DataFrame(
                    {
                        "Open": [150.0],
                        "High": [155.0],
                        "Low": [149.0],
                        "Close": [152.0],
                        "Volume": [1000000],
                    },
                    index=pd.date_range("2024-01-01", periods=1, freq="D"),
                )

                mock_ticker.history.return_value = mock_hist_df
                mock_yf.Ticker.return_value = mock_ticker

                provider = YfinanceProvider()
                query = DataQuery(
                    asset=AssetType.STOCK,
                    symbols=["AAPL", "GOOGL"],  # Multiple symbols
                )

                response = await provider.get_data(query)
                assert response is not None
                # Should have data from fallback individual requests
                assert len(response.data) >= 1

    @pytest.mark.asyncio
    async def test_yfinance_get_quote(self):
        """Test yfinance real-time quote functionality."""
        with patch("vprism.core.providers.yfinance_provider.YFINANCE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.yfinance_provider.yf", create=True
            ) as mock_yf:
                from vprism.core.providers.yfinance_provider import YfinanceProvider

                # Mock ticker with minute data
                mock_ticker = Mock()
                mock_hist_df = pd.DataFrame(
                    {
                        "Open": [150.0],
                        "High": [155.0],
                        "Low": [149.0],
                        "Close": [152.0],
                        "Volume": [1000000],
                    },
                    index=pd.date_range("2024-01-01 09:30:00", periods=1, freq="1min"),
                )

                mock_ticker.history.return_value = mock_hist_df
                mock_yf.Ticker.return_value = mock_ticker

                provider = YfinanceProvider()
                quote = await provider.get_quote("AAPL")

                assert quote is not None
                assert quote.symbol == "AAPL"
                assert quote.close == Decimal("152.0")

    def test_yfinance_get_options_chain(self):
        """Test yfinance options chain functionality."""
        with patch("vprism.core.providers.yfinance_provider.YFINANCE_AVAILABLE", True):
            with patch(
                "vprism.core.providers.yfinance_provider.yf", create=True
            ) as mock_yf:
                from vprism.core.providers.yfinance_provider import YfinanceProvider

                # Mock ticker with options
                mock_ticker = Mock()
                mock_ticker.options = ["2024-01-19", "2024-02-16"]

                # Mock option chain
                mock_option_chain = Mock()
                mock_option_chain.calls = pd.DataFrame(
                    {"strike": [150.0, 155.0], "lastPrice": [5.0, 2.5]}
                )
                mock_option_chain.puts = pd.DataFrame(
                    {"strike": [150.0, 155.0], "lastPrice": [3.0, 6.0]}
                )

                mock_ticker.option_chain.return_value = mock_option_chain
                mock_yf.Ticker.return_value = mock_ticker

                provider = YfinanceProvider()
                options = provider.get_options_chain("AAPL")

                assert options["symbol"] == "AAPL"
                assert len(options["expiration_dates"]) == 2
                assert len(options["calls"]) == 2
                assert len(options["puts"]) == 2

    @pytest.mark.asyncio
    async def test_alpha_vantage_additional_assets(self):
        """Test Alpha Vantage with additional asset types."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        provider = AlphaVantageProvider(api_key="test_key")

        # Test crypto parameters
        query = DataQuery(
            asset=AssetType.CRYPTO, symbols=["BTC"], timeframe=TimeFrame.MINUTE_5
        )

        params = provider._build_request_params(query)
        assert params["function"] == "CRYPTO_INTRADAY"
        assert params["interval"] == "5min"
        assert params["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_alpha_vantage_get_quote(self):
        """Test Alpha Vantage real-time quote functionality."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        provider = AlphaVantageProvider(api_key="test_key")

        # Mock HTTP client response
        mock_response = Mock()
        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "02. open": "150.00",
                "03. high": "155.00",
                "04. low": "149.00",
                "05. price": "152.00",
                "06. volume": "1000000",
                "08. previous close": "151.00",
                "09. change": "1.00",
                "10. change percent": "0.66%",
            }
        }
        mock_response.raise_for_status.return_value = None

        # Mock the HTTP client's get method directly
        with patch(
            "vprism.core.http_adapter.HttpClient.get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            quote = await provider.get_quote("AAPL")

            assert quote is not None
            assert quote.symbol == "AAPL"
            assert quote.close == Decimal("152.00")
            assert quote.extra_fields["change"] == "1.00"

    @pytest.mark.asyncio
    async def test_alpha_vantage_symbol_search(self):
        """Test Alpha Vantage symbol search functionality."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider

        provider = AlphaVantageProvider(api_key="test_key")

        # Mock HTTP client response
        mock_response = Mock()
        mock_response.json.return_value = {
            "bestMatches": [
                {
                    "1. symbol": "AAPL",
                    "2. name": "Apple Inc.",
                    "3. type": "Equity",
                    "4. region": "United States",
                    "8. currency": "USD",
                    "9. matchScore": "1.0000",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        # Mock the HTTP client's get method directly
        with patch(
            "vprism.core.http_adapter.HttpClient.get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            results = await provider.search_symbols("Apple")

            assert len(results) == 1
            assert results[0]["symbol"] == "AAPL"
            assert results[0]["name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_provider_streaming_with_rate_limits(self):
        """Test provider streaming behavior with rate limits."""
        from vprism.core.providers.alpha_vantage_provider import AlphaVantageProvider
        from vprism.core.exceptions import RateLimitException

        provider = AlphaVantageProvider(api_key="test_key")

        query = DataQuery(asset=AssetType.STOCK, symbols=["AAPL"])

        # Mock get_data to raise rate limit exception first, then succeed
        call_count = 0

        async def mock_get_data(q):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitException(provider="alpha_vantage")
            else:
                # Return mock response
                from vprism.core.models import (
                    DataResponse,
                    DataPoint,
                    ResponseMetadata,
                    ProviderInfo,
                )

                return DataResponse(
                    data=[
                        DataPoint(
                            symbol="AAPL",
                            timestamp=datetime.now(),
                            close=Decimal("150.0"),
                        )
                    ],
                    metadata=ResponseMetadata(
                        query_time=datetime.now(),
                        execution_time_ms=100,
                        record_count=1,
                        cache_hit=False,
                    ),
                    source=ProviderInfo(name="alpha_vantage"),
                    query=q,
                )

        with patch.object(provider, "get_data", side_effect=mock_get_data):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Test streaming - should handle rate limit gracefully
                stream_gen = provider.stream_data(query)

                # Get first item (should trigger rate limit handling)
                try:
                    first_item = await stream_gen.__anext__()
                    assert first_item.symbol == "AAPL"

                    # Verify that sleep was called for rate limit handling
                    mock_sleep.assert_called()

                except StopAsyncIteration:
                    pass  # Expected if stream ends
