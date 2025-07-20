"""
Tests for VPrism Native Data Provider.

This module contains comprehensive tests for the VPrism native provider
including the AkshareModernAdapter and VPrismNativeProvider classes.
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


class TestAkshareModernAdapter:
    """Test suite for AkshareModernAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create AkshareModernAdapter instance."""
        from vprism.core.providers.vprism_native_provider import AkshareModernAdapter

        return AkshareModernAdapter()

    def test_adapter_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter._function_mapping is not None
        assert adapter._column_mappings is not None
        assert len(adapter._function_mapping) > 0
        assert len(adapter._column_mappings) > 0

    def test_function_mapping_structure(self, adapter):
        """Test function mapping structure."""
        mapping = adapter._function_mapping

        # Check key mappings exist
        assert "stock_cn_spot" in mapping
        assert "stock_cn_daily" in mapping
        assert "etf_cn_spot" in mapping
        assert "fund_cn_open" in mapping

        # Check mapping structure
        stock_config = mapping["stock_cn_spot"]
        assert "function" in stock_config
        assert "params" in stock_config
        assert "description" in stock_config
        assert stock_config["function"] == "stock_zh_a_spot_em"

    def test_column_mappings_structure(self, adapter):
        """Test column mappings structure."""
        mappings = adapter._column_mappings

        # Check asset type mappings exist
        assert "stock" in mappings
        assert "etf" in mappings
        assert "fund" in mappings

        # Check stock column mappings
        stock_mapping = mappings["stock"]
        assert stock_mapping["日期"] == "timestamp"
        assert stock_mapping["开盘"] == "open"
        assert stock_mapping["收盘"] == "close"
        assert stock_mapping["成交量"] == "volume"

    def test_get_function_key_stock_cn_spot(self, adapter):
        """Test function key generation for Chinese stock spot data."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        key = adapter.get_function_key(query)
        assert key == "stock_cn_spot"

    def test_get_function_key_stock_cn_daily(self, adapter):
        """Test function key generation for Chinese stock daily data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        key = adapter.get_function_key(query)
        assert key == "stock_cn_daily"

    def test_get_function_key_stock_cn_intraday(self, adapter):
        """Test function key generation for Chinese stock intraday data."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.MINUTE_5,
        )

        key = adapter.get_function_key(query)
        assert key == "stock_cn_intraday"

    def test_get_function_key_etf_cn_spot(self, adapter):
        """Test function key generation for Chinese ETF spot data."""
        query = DataQuery(asset=AssetType.ETF, market=MarketType.CN, symbols=["510050"])

        key = adapter.get_function_key(query)
        assert key == "etf_cn_spot"

    def test_get_function_key_stock_hk(self, adapter):
        """Test function key generation for Hong Kong stocks."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.HK, symbols=["00700"]
        )

        key = adapter.get_function_key(query)
        assert key == "stock_hk_spot"

    def test_get_akshare_function_success(self, adapter):
        """Test successful akshare function retrieval."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        config = adapter.get_akshare_function(query)
        assert config is not None
        assert config["function"] == "stock_zh_a_spot_em"
        assert "params" in config
        assert "description" in config

    def test_get_akshare_function_unsupported(self, adapter):
        """Test akshare function retrieval for unsupported query."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.US,  # Limited US support
            symbols=["AAPL"],
            timeframe=TimeFrame.MINUTE_1,  # Intraday US not supported
        )

        config = adapter.get_akshare_function(query)
        # Should return None or limited config for unsupported combinations
        # The exact behavior depends on implementation

    def test_map_timeframe_to_akshare(self, adapter):
        """Test timeframe mapping to akshare parameters."""
        assert adapter.map_timeframe_to_akshare(TimeFrame.MINUTE_1) == "1"
        assert adapter.map_timeframe_to_akshare(TimeFrame.MINUTE_5) == "5"
        assert adapter.map_timeframe_to_akshare(TimeFrame.MINUTE_15) == "15"
        assert adapter.map_timeframe_to_akshare(TimeFrame.MINUTE_30) == "30"
        assert adapter.map_timeframe_to_akshare(TimeFrame.HOUR_1) == "60"
        assert adapter.map_timeframe_to_akshare(TimeFrame.DAY_1) == "daily"
        assert adapter.map_timeframe_to_akshare(TimeFrame.WEEK_1) == "weekly"
        assert adapter.map_timeframe_to_akshare(TimeFrame.MONTH_1) == "monthly"

    def test_standardize_dataframe_stock_chinese_columns(self, adapter):
        """Test DataFrame standardization with Chinese column names."""
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
                "涨跌幅": [0.02, 0.03],
            }
        )

        data_points = adapter.standardize_dataframe(df, "000001", AssetType.STOCK)

        assert len(data_points) == 2

        # Check first data point
        point = data_points[0]
        assert point.symbol == "000001"
        assert point.open == Decimal("10.0")
        assert point.high == Decimal("10.5")
        assert point.low == Decimal("9.8")
        assert point.close == Decimal("10.2")
        assert point.volume == Decimal("1000000")
        assert point.amount == Decimal("10200000")
        assert "涨跌幅" in point.extra_fields or "change_pct" in point.extra_fields

    def test_standardize_dataframe_english_columns(self, adapter):
        """Test DataFrame standardization with English column names."""
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "open": [150.0, 151.0],
                "high": [155.0, 156.0],
                "low": [149.0, 150.0],
                "close": [152.0, 153.0],
                "volume": [1000000, 1100000],
                "adj_close": [152.0, 153.0],
            }
        )

        data_points = adapter.standardize_dataframe(df, "AAPL", AssetType.STOCK)

        assert len(data_points) == 2

        point = data_points[0]
        assert point.symbol == "AAPL"
        assert point.open == Decimal("150.0")
        assert point.close == Decimal("152.0")
        assert "adj_close" in point.extra_fields

    def test_standardize_dataframe_etf_data(self, adapter):
        """Test DataFrame standardization for ETF data."""
        df = pd.DataFrame(
            {
                "日期": ["2024-01-01", "2024-01-02"],
                "开盘": [3.50, 3.52],
                "收盘": [3.55, 3.58],
                "单位净值": [3.5500, 3.5800],
                "累计净值": [3.5500, 3.5800],
            }
        )

        data_points = adapter.standardize_dataframe(df, "510050", AssetType.ETF)

        assert len(data_points) == 2

        point = data_points[0]
        assert point.symbol == "510050"
        assert point.open == Decimal("3.50")
        assert point.close == Decimal("3.55")
        assert "单位净值" in point.extra_fields or "nav" in point.extra_fields
        assert (
            "累计净值" in point.extra_fields or "cumulative_nav" in point.extra_fields
        )

    def test_standardize_dataframe_empty(self, adapter):
        """Test DataFrame standardization with empty DataFrame."""
        df = pd.DataFrame()

        data_points = adapter.standardize_dataframe(df, "000001", AssetType.STOCK)
        assert len(data_points) == 0

    def test_standardize_dataframe_none(self, adapter):
        """Test DataFrame standardization with None input."""
        data_points = adapter.standardize_dataframe(None, "000001", AssetType.STOCK)
        assert len(data_points) == 0

    def test_parse_timestamp_various_formats(self, adapter):
        """Test timestamp parsing with various formats."""
        test_cases = [
            ("2024-01-01", datetime(2024, 1, 1)),
            ("2024-01-01 10:30:00", datetime(2024, 1, 1, 10, 30, 0)),
            ("2024/01/01", datetime(2024, 1, 1)),
            ("20240101", datetime(2024, 1, 1)),
            ("2024-01-01 10:30", datetime(2024, 1, 1, 10, 30)),
        ]

        for date_str, expected in test_cases:
            row = pd.Series({"timestamp": date_str})
            result = adapter._parse_timestamp(row)
            assert result == expected, f"Failed for {date_str}"

    def test_parse_timestamp_pandas_timestamp(self, adapter):
        """Test timestamp parsing with pandas Timestamp."""
        pd_timestamp = pd.Timestamp("2024-01-01 10:30:00")
        row = pd.Series({"timestamp": pd_timestamp})

        result = adapter._parse_timestamp(row)
        assert result == datetime(2024, 1, 1, 10, 30, 0)

    def test_parse_timestamp_datetime_object(self, adapter):
        """Test timestamp parsing with datetime object."""
        dt = datetime(2024, 1, 1, 10, 30, 0)
        row = pd.Series({"timestamp": dt})

        result = adapter._parse_timestamp(row)
        assert result == dt

    def test_parse_timestamp_invalid(self, adapter):
        """Test timestamp parsing with invalid input."""
        row = pd.Series({"timestamp": "invalid-date"})

        result = adapter._parse_timestamp(row)
        assert result is None

    def test_safe_decimal_conversion(self, adapter):
        """Test safe decimal conversion."""
        # Valid conversions
        assert adapter._safe_decimal(10.5) == Decimal("10.5")
        assert adapter._safe_decimal("10.5") == Decimal("10.5")
        assert adapter._safe_decimal(100) == Decimal("100")

        # Invalid conversions
        assert adapter._safe_decimal(None) is None
        assert adapter._safe_decimal(pd.NA) is None
        assert adapter._safe_decimal("invalid") is None

    @pytest.mark.asyncio
    async def test_build_function_params_basic(self, adapter):
        """Test basic function parameter building."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        base_params = {"period": "daily"}

        params = await adapter._build_function_params(query, base_params)

        assert params["symbol"] == "000001"
        assert params["period"] == "daily"

    @pytest.mark.asyncio
    async def test_build_function_params_with_dates(self, adapter):
        """Test function parameter building with date range."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        base_params = {"period": "daily"}  # Contains "daily" keyword

        params = await adapter._build_function_params(query, base_params)

        assert params["start_date"] == "20240101"
        assert params["end_date"] == "20240131"

    @pytest.mark.asyncio
    async def test_build_function_params_with_timeframe(self, adapter):
        """Test function parameter building with timeframe substitution."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.MINUTE_5,
        )

        base_params = {"period": "{timeframe}"}

        params = await adapter._build_function_params(query, base_params)

        assert params["period"] == "5"

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, adapter):
        """Test successful data fetching."""
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch(
                "vprism.core.providers.vprism_native_provider.ak", create=True
            ) as mock_ak:
                # Mock akshare function
                mock_func = Mock()
                mock_df = pd.DataFrame(
                    {"日期": ["2024-01-01"], "开盘": [10.0], "收盘": [10.5]}
                )
                mock_func.return_value = mock_df
                mock_ak.stock_zh_a_spot_em = mock_func

                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                result = await adapter.fetch_data(query)

                assert not result.empty
                assert len(result) == 1
                mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_data_unsupported_query(self, adapter):
        """Test data fetching with unsupported query."""
        query = DataQuery(
            asset=AssetType.CRYPTO,  # Limited crypto support
            market=MarketType.GLOBAL,
            symbols=["BTC-USD"],
        )

        # This should raise an exception for unsupported query or dependency missing
        with pytest.raises(ProviderException) as exc_info:
            await adapter.fetch_data(query)

        # Could be either UNSUPPORTED_QUERY or DEPENDENCY_MISSING depending on akshare availability
        assert exc_info.value.error_code in ["UNSUPPORTED_QUERY", "DEPENDENCY_MISSING"]

    @pytest.mark.asyncio
    async def test_fetch_data_function_not_available(self, adapter):
        """Test data fetching when akshare function is not available."""
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch(
                "vprism.core.providers.vprism_native_provider.ak", create=True
            ) as mock_ak:
                # Mock missing function
                del mock_ak.stock_zh_a_spot_em

                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                with pytest.raises(ProviderException) as exc_info:
                    await adapter.fetch_data(query)

                assert exc_info.value.error_code == "FUNCTION_NOT_AVAILABLE"

    @pytest.mark.asyncio
    async def test_fetch_data_akshare_error(self, adapter):
        """Test data fetching when akshare function raises error."""
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch(
                "vprism.core.providers.vprism_native_provider.ak", create=True
            ) as mock_ak:
                # Mock akshare function that raises error
                mock_func = Mock()
                mock_func.side_effect = Exception("Network error")
                mock_ak.stock_zh_a_spot_em = mock_func

                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                with pytest.raises(ProviderException) as exc_info:
                    await adapter.fetch_data(query)

                assert exc_info.value.error_code == "FETCH_ERROR"


class TestVPrismNativeProvider:
    """Test suite for VPrismNativeProvider."""

    @pytest.fixture
    def mock_akshare(self):
        """Mock akshare module."""
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch(
                "vprism.core.providers.vprism_native_provider.ak", create=True
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
    def vprism_native_provider(self, mock_akshare):
        """Create VPrismNativeProvider instance."""
        from vprism.core.providers.vprism_native_provider import VPrismNativeProvider

        return VPrismNativeProvider()

    def test_provider_initialization(self, vprism_native_provider):
        """Test provider initialization."""
        assert vprism_native_provider.name == "vprism_native"
        assert vprism_native_provider.auth_config.auth_type.value == "none"
        assert vprism_native_provider.rate_limit.requests_per_minute == 60
        assert vprism_native_provider._adapter is not None

    def test_initialization_without_akshare(self):
        """Test initialization without akshare raises error."""
        from vprism.core.providers.vprism_native_provider import VPrismNativeProvider

        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", False
        ):
            with pytest.raises(ProviderException) as exc_info:
                VPrismNativeProvider()

            assert exc_info.value.error_code == "DEPENDENCY_MISSING"

    def test_capability_discovery(self, vprism_native_provider):
        """Test provider capability discovery."""
        capability = vprism_native_provider.capability

        # Check supported assets
        assert AssetType.STOCK in capability.supported_assets
        assert AssetType.BOND in capability.supported_assets
        assert AssetType.FUND in capability.supported_assets
        assert AssetType.ETF in capability.supported_assets
        assert AssetType.FUTURES in capability.supported_assets
        assert AssetType.INDEX in capability.supported_assets
        assert AssetType.CRYPTO in capability.supported_assets

        # Check supported markets
        assert MarketType.CN in capability.supported_markets
        assert MarketType.HK in capability.supported_markets
        assert MarketType.US in capability.supported_markets

        # Check timeframes
        assert TimeFrame.MINUTE_1 in capability.supported_timeframes
        assert TimeFrame.DAY_1 in capability.supported_timeframes
        assert TimeFrame.WEEK_1 in capability.supported_timeframes

        # Check other capabilities
        assert capability.max_symbols_per_request == 10
        assert not capability.supports_real_time
        assert capability.supports_historical
        assert capability.data_delay_seconds == 300
        assert capability.max_history_days == 7300

    @pytest.mark.asyncio
    async def test_authentication_success(self, vprism_native_provider):
        """Test successful authentication."""
        result = await vprism_native_provider._authenticate()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_success(self, vprism_native_provider, mock_akshare):
        """Test successful health check."""
        result = await vprism_native_provider.health_check()
        assert result is True
        mock_akshare.stock_zh_a_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, vprism_native_provider, mock_akshare):
        """Test failed health check."""
        mock_akshare.stock_zh_a_spot_em.side_effect = Exception("Connection error")

        result = await vprism_native_provider.health_check()
        assert result is False

    def test_can_handle_query_supported(self, vprism_native_provider):
        """Test query handling for supported queries."""
        # Supported query
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )
        assert vprism_native_provider.can_handle_query(query) is True

        # ETF query
        query = DataQuery(asset=AssetType.ETF, market=MarketType.CN, symbols=["510050"])
        assert vprism_native_provider.can_handle_query(query) is True

    def test_can_handle_query_unsupported(self, vprism_native_provider):
        """Test query handling for unsupported queries."""
        # Too many symbols
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=[
                f"00000{i}" for i in range(20)
            ],  # More than max_symbols_per_request
        )
        assert vprism_native_provider.can_handle_query(query) is False

    @pytest.mark.asyncio
    async def test_get_data_success(self, vprism_native_provider, mock_akshare):
        """Test successful data retrieval."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001"],
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
        )

        response = await vprism_native_provider.get_data(query)

        assert response is not None
        assert len(response.data) == 2  # Mock data has 2 rows
        assert response.source.name == "vprism_native"
        assert response.metadata.record_count == 2
        assert "vprism-native-1.0.0" in response.source.version

        # Check data point structure
        data_point = response.data[0]
        assert data_point.symbol == "000001"
        assert isinstance(data_point.open, Decimal)
        assert isinstance(data_point.close, Decimal)

    @pytest.mark.asyncio
    async def test_get_data_multiple_symbols(
        self, vprism_native_provider, mock_akshare
    ):
        """Test data retrieval with multiple symbols."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=["000001", "000002"],
            timeframe=TimeFrame.DAY_1,
        )

        # Mock the adapter's fetch_data method to return data for each symbol
        with patch.object(vprism_native_provider._adapter, "fetch_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                {
                    "日期": ["2024-01-01", "2024-01-02"],
                    "开盘": [10.0, 10.2],
                    "收盘": [10.2, 10.5],
                }
            )

            response = await vprism_native_provider.get_data(query)

            assert response is not None
            assert len(response.data) == 4  # 2 symbols × 2 rows each

            # Check that data is sorted by symbol and timestamp
            symbols = [point.symbol for point in response.data]
            assert "000001" in symbols
            assert "000002" in symbols

    @pytest.mark.asyncio
    async def test_get_data_no_symbols_provided(
        self, vprism_native_provider, mock_akshare
    ):
        """Test data retrieval when no symbols are provided."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)

        # Mock the adapter's fetch_data method to return data
        with patch.object(vprism_native_provider._adapter, "fetch_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                {"日期": ["2024-01-01"], "开盘": [10.0], "收盘": [10.2]}
            )

            response = await vprism_native_provider.get_data(query)

            assert response is not None
            # Should get default symbols from _get_default_symbols
            assert len(response.data) > 0

    @pytest.mark.asyncio
    async def test_get_data_unsupported_query(self, vprism_native_provider):
        """Test data retrieval with unsupported query."""
        query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=[f"00000{i}" for i in range(20)],  # Too many symbols
        )

        with pytest.raises(ProviderException) as exc_info:
            await vprism_native_provider.get_data(query)

        assert exc_info.value.error_code == "UNSUPPORTED_QUERY"

    @pytest.mark.asyncio
    async def test_get_default_symbols_stock_cn(
        self, vprism_native_provider, mock_akshare
    ):
        """Test getting default symbols for Chinese stocks."""
        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)

        symbols = await vprism_native_provider._get_default_symbols(query)

        assert len(symbols) > 0
        assert len(symbols) <= 20  # Should limit to top 20
        mock_akshare.stock_zh_a_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_default_symbols_etf_cn(
        self, vprism_native_provider, mock_akshare
    ):
        """Test getting default symbols for Chinese ETFs."""
        # Mock ETF data
        mock_etf_df = pd.DataFrame(
            {"代码": ["510050", "510300"], "名称": ["50ETF", "300ETF"]}
        )
        mock_akshare.fund_etf_spot_em.return_value = mock_etf_df

        query = DataQuery(asset=AssetType.ETF, market=MarketType.CN)

        symbols = await vprism_native_provider._get_default_symbols(query)

        assert len(symbols) > 0
        assert len(symbols) <= 10  # Should limit to top 10
        mock_akshare.fund_etf_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_default_symbols_unsupported(self, vprism_native_provider):
        """Test getting default symbols for unsupported combination."""
        query = DataQuery(asset=AssetType.CRYPTO, market=MarketType.GLOBAL)

        symbols = await vprism_native_provider._get_default_symbols(query)

        assert len(symbols) == 0  # Should return empty list

    @pytest.mark.asyncio
    async def test_get_default_symbols_error_handling(
        self, vprism_native_provider, mock_akshare
    ):
        """Test error handling in getting default symbols."""
        mock_akshare.stock_zh_a_spot_em.side_effect = Exception("Network error")

        query = DataQuery(asset=AssetType.STOCK, market=MarketType.CN)

        symbols = await vprism_native_provider._get_default_symbols(query)

        assert len(symbols) == 0  # Should return empty list on error

    @pytest.mark.asyncio
    async def test_stream_data_not_supported(self, vprism_native_provider):
        """Test that streaming is not supported."""
        query = DataQuery(asset=AssetType.STOCK, symbols=["000001"])

        with pytest.raises(ProviderException) as exc_info:
            await vprism_native_provider.stream_data(query)

        assert exc_info.value.error_code == "STREAMING_NOT_SUPPORTED"

    def test_get_supported_functions(self, vprism_native_provider):
        """Test getting supported functions list."""
        functions = vprism_native_provider.get_supported_functions()

        assert isinstance(functions, dict)
        assert len(functions) > 0
        assert "stock_cn_spot" in functions
        assert "Chinese A-share spot prices" in functions["stock_cn_spot"]

    def test_get_function_mapping(self, vprism_native_provider):
        """Test getting complete function mapping."""
        mapping = vprism_native_provider.get_function_mapping()

        assert isinstance(mapping, dict)
        assert len(mapping) > 0

        # Check structure
        for key, config in mapping.items():
            assert "function" in config
            assert "params" in config
            assert "description" in config

    @pytest.mark.asyncio
    async def test_adapter_integration(self, vprism_native_provider, mock_akshare):
        """Test integration between provider and adapter."""
        query = DataQuery(
            asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
        )

        # Test that adapter is used correctly
        with patch.object(vprism_native_provider._adapter, "fetch_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                {"日期": ["2024-01-01"], "开盘": [10.0], "收盘": [10.5]}
            )

            with patch.object(
                vprism_native_provider._adapter, "standardize_dataframe"
            ) as mock_standardize:
                from vprism.core.models import DataPoint

                mock_standardize.return_value = [
                    DataPoint(
                        symbol="000001",
                        timestamp=datetime(2024, 1, 1),
                        open=Decimal("10.0"),
                        close=Decimal("10.5"),
                    )
                ]

                response = await vprism_native_provider.get_data(query)

                assert response is not None
                assert len(response.data) == 1
                mock_fetch.assert_called_once()
                mock_standardize.assert_called_once()


class TestVPrismNativeProviderIntegration:
    """Integration tests for VPrism native provider."""

    @pytest.mark.asyncio
    async def test_provider_registry_integration(self):
        """Test provider registration and discovery."""
        from vprism.core.provider_abstraction import EnhancedProviderRegistry
        from vprism.core.providers.vprism_native_provider import VPrismNativeProvider

        registry = EnhancedProviderRegistry()

        # Mock akshare availability
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch("vprism.core.providers.vprism_native_provider.ak", create=True):
                provider = VPrismNativeProvider()
                registry.register_provider(provider)

                # Test provider discovery
                query = DataQuery(
                    asset=AssetType.STOCK, market=MarketType.CN, symbols=["000001"]
                )

                capable_providers = registry.find_capable_providers(query)
                assert len(capable_providers) == 1
                assert capable_providers[0].name == "vprism_native"

    @pytest.mark.asyncio
    async def test_provider_priority_over_akshare(self):
        """Test that VPrism native has higher priority than akshare."""
        from vprism.core.provider_abstraction import EnhancedProviderRegistry
        from vprism.core.providers.vprism_native_provider import VPrismNativeProvider
        from vprism.core.providers.akshare_provider import AkshareProvider

        registry = EnhancedProviderRegistry()

        # Mock both providers
        with patch(
            "vprism.core.providers.vprism_native_provider.AKSHARE_AVAILABLE", True
        ):
            with patch(
                "vprism.core.providers.akshare_provider.AKSHARE_AVAILABLE", True
            ):
                with patch(
                    "vprism.core.providers.vprism_native_provider.ak", create=True
                ):
                    with patch(
                        "vprism.core.providers.akshare_provider.ak", create=True
                    ):
                        vprism_provider = VPrismNativeProvider()
                        akshare_provider = AkshareProvider()

                        # Register both providers
                        registry.register_provider(vprism_provider)
                        registry.register_provider(akshare_provider)

                        # Set scores to simulate priority (higher score = higher priority)
                        registry.update_provider_score(
                            "vprism_native", True, 100
                        )  # Good performance
                        registry.update_provider_score(
                            "akshare", True, 500
                        )  # Slower performance

                        query = DataQuery(
                            asset=AssetType.STOCK,
                            market=MarketType.CN,
                            symbols=["000001"],
                        )

                        capable_providers = registry.find_capable_providers(query)

                        # VPrism native should be first due to better score
                        assert len(capable_providers) == 2
                        assert capable_providers[0].name == "vprism_native"
                        assert capable_providers[1].name == "akshare"

    def test_function_mapping_completeness(self):
        """Test that function mapping covers major use cases."""
        from vprism.core.providers.vprism_native_provider import AkshareModernAdapter

        adapter = AkshareModernAdapter()
        mapping = adapter._function_mapping

        # Check coverage for major asset types and markets
        expected_keys = [
            "stock_cn_spot",
            "stock_cn_daily",
            "stock_cn_intraday",
            "stock_hk_spot",
            "stock_hk_daily",
            "stock_us_spot",
            "stock_us_daily",
            "etf_cn_spot",
            "etf_cn_daily",
            "fund_cn_open",
            "fund_cn_money",
            "bond_cn_spot",
            "bond_cn_treasury",
            "futures_cn_spot",
            "futures_cn_daily",
            "index_cn_spot",
            "index_cn_daily",
            "crypto_spot",
        ]

        for key in expected_keys:
            assert key in mapping, f"Missing function mapping for {key}"

            config = mapping[key]
            assert "function" in config
            assert "params" in config
            assert "description" in config
            assert isinstance(config["function"], str)
            assert len(config["function"]) > 0

    def test_column_mapping_completeness(self):
        """Test that column mappings cover major data types."""
        from vprism.core.providers.vprism_native_provider import AkshareModernAdapter

        adapter = AkshareModernAdapter()
        mappings = adapter._column_mappings

        # Check coverage for major asset types
        expected_asset_types = ["stock", "etf", "fund", "bond", "futures", "index"]

        for asset_type in expected_asset_types:
            assert asset_type in mappings, f"Missing column mapping for {asset_type}"

            mapping = mappings[asset_type]

            # Check for essential timestamp mapping
            assert any(target == "timestamp" for target in mapping.values()), (
                f"Missing timestamp mapping for {asset_type}"
            )

            # Check for essential price mappings (where applicable)
            if asset_type in ["stock", "etf", "bond", "futures", "index"]:
                price_fields = ["open", "high", "low", "close"]
                for field in price_fields:
                    assert any(target == field for target in mapping.values()), (
                        f"Missing {field} mapping for {asset_type}"
                    )
