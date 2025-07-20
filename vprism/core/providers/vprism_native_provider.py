"""
VPrism Native Data Provider Implementation.

This module implements the VPrism native data provider, which is a modern
refactoring of akshare functionality. It provides a unified interface to
akshare's 1000+ functions through a modern, composable API design.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from vprism.core.exceptions import ProviderException
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ProviderInfo,
    ResponseMetadata,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    EnhancedDataProvider,
    ProviderCapability,
    RateLimitConfig,
)

logger = logging.getLogger(__name__)

# Optional import for akshare
try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("akshare not available - VPrismNativeProvider will be disabled")


class AkshareModernAdapter:
    """
    Modern adapter for akshare's 1000+ functions.

    This adapter provides a unified interface to akshare functions,
    mapping modern query parameters to specific akshare function calls.
    """

    def __init__(self):
        """Initialize the akshare modern adapter."""
        self._function_mapping = self._build_function_mapping()
        self._column_mappings = self._build_column_mappings()

    def _build_function_mapping(self) -> dict[str, dict[str, Any]]:
        """
        Build comprehensive mapping from query parameters to akshare functions.

        Returns:
            Dictionary mapping query patterns to akshare function configurations
        """
        return {
            # Stock data mappings
            "stock_cn_spot": {
                "function": "stock_zh_a_spot_em",
                "params": {},
                "description": "Chinese A-share spot prices",
            },
            "stock_cn_daily": {
                "function": "stock_zh_a_hist",
                "params": {"period": "daily", "adjust": ""},
                "description": "Chinese A-share daily historical data",
            },
            "stock_cn_intraday": {
                "function": "stock_zh_a_hist_min_em",
                "params": {"period": "{timeframe}"},
                "description": "Chinese A-share intraday data",
            },
            "stock_hk_spot": {
                "function": "stock_hk_spot_em",
                "params": {},
                "description": "Hong Kong stock spot prices",
            },
            "stock_hk_daily": {
                "function": "stock_hk_hist",
                "params": {"period": "daily", "adjust": ""},
                "description": "Hong Kong stock daily historical data",
            },
            "stock_us_spot": {
                "function": "stock_us_spot_em",
                "params": {},
                "description": "US stock spot prices",
            },
            "stock_us_daily": {
                "function": "stock_us_hist",
                "params": {"period": "daily", "adjust": ""},
                "description": "US stock daily historical data",
            },
            # ETF data mappings
            "etf_cn_spot": {
                "function": "fund_etf_spot_em",
                "params": {},
                "description": "Chinese ETF spot prices",
            },
            "etf_cn_daily": {
                "function": "fund_etf_hist_em",
                "params": {"period": "daily"},
                "description": "Chinese ETF daily historical data",
            },
            # Fund data mappings
            "fund_cn_open": {
                "function": "fund_open_fund_info_em",
                "params": {"indicator": "累计净值走势"},
                "description": "Chinese open-end fund data",
            },
            "fund_cn_money": {
                "function": "fund_money_fund_info_em",
                "params": {},
                "description": "Chinese money market fund data",
            },
            # Bond data mappings
            "bond_cn_spot": {
                "function": "bond_zh_hs_cov_spot",
                "params": {},
                "description": "Chinese convertible bond spot prices",
            },
            "bond_cn_treasury": {
                "function": "bond_zh_us_rate",
                "params": {},
                "description": "Chinese treasury bond rates",
            },
            # Futures data mappings
            "futures_cn_spot": {
                "function": "futures_zh_spot",
                "params": {},
                "description": "Chinese futures spot prices",
            },
            "futures_cn_daily": {
                "function": "futures_zh_daily_sina",
                "params": {},
                "description": "Chinese futures daily data",
            },
            # Index data mappings
            "index_cn_spot": {
                "function": "stock_zh_index_spot_em",
                "params": {},
                "description": "Chinese stock index spot data",
            },
            "index_cn_daily": {
                "function": "stock_zh_index_daily_em",
                "params": {},
                "description": "Chinese stock index daily data",
            },
            # Crypto data mappings (limited akshare support)
            "crypto_spot": {
                "function": "crypto_js_spot",
                "params": {},
                "description": "Cryptocurrency spot prices",
            },
        }

    def _build_column_mappings(self) -> dict[str, dict[str, str]]:
        """
        Build column name mappings for different data types.

        Returns:
            Dictionary mapping data types to column name mappings
        """
        return {
            "stock": {
                # Chinese column names to English
                "日期": "timestamp",
                "时间": "timestamp",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "change_pct",
                "涨跌额": "change_amount",
                "换手率": "turnover_rate",
                # English column names (standardization)
                "date": "timestamp",
                "datetime": "timestamp",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "amount",
                "adj_close": "adj_close",
            },
            "etf": {
                "日期": "timestamp",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "单位净值": "nav",
                "累计净值": "cumulative_nav",
            },
            "fund": {
                "净值日期": "timestamp",
                "单位净值": "nav",
                "累计净值": "cumulative_nav",
                "日增长率": "daily_return",
                "申购状态": "purchase_status",
                "赎回状态": "redemption_status",
            },
            "bond": {
                "日期": "timestamp",
                "开盘价": "open",
                "最高价": "high",
                "最低价": "low",
                "收盘价": "close",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "change_pct",
            },
            "futures": {
                "日期": "timestamp",
                "开盘价": "open",
                "最高价": "high",
                "最低价": "low",
                "收盘价": "close",
                "成交量": "volume",
                "持仓量": "open_interest",
                "涨跌": "change_amount",
                "涨跌幅": "change_pct",
            },
            "index": {
                "日期": "timestamp",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "change_pct",
                "涨跌额": "change_amount",
            },
        }

    def get_function_key(self, query: DataQuery) -> str:
        """
        Generate function key based on query parameters.

        Args:
            query: Data query object

        Returns:
            Function key for mapping lookup
        """
        asset_map = {
            AssetType.STOCK: "stock",
            AssetType.ETF: "etf",
            AssetType.FUND: "fund",
            AssetType.BOND: "bond",
            AssetType.FUTURES: "futures",
            AssetType.INDEX: "index",
            AssetType.CRYPTO: "crypto",
        }

        market_map = {
            MarketType.CN: "cn",
            MarketType.HK: "hk",
            MarketType.US: "us",
            MarketType.GLOBAL: "global",
        }

        asset_str = asset_map.get(query.asset, "stock")
        market_str = market_map.get(query.market, "cn")

        # Determine data type (spot, daily, intraday)
        if query.timeframe and query.timeframe != TimeFrame.DAY_1:
            data_type = "intraday"
        elif query.start or query.end:
            data_type = "daily"
        else:
            data_type = "spot"

        # Build function key
        if market_str == "global":
            return f"{asset_str}_{data_type}"
        else:
            return f"{asset_str}_{market_str}_{data_type}"

    def get_akshare_function(self, query: DataQuery) -> dict[str, Any] | None:
        """
        Get akshare function configuration for query.

        Args:
            query: Data query object

        Returns:
            Function configuration or None if not supported
        """
        function_key = self.get_function_key(query)
        return self._function_mapping.get(function_key)

    def map_timeframe_to_akshare(self, timeframe: TimeFrame) -> str:
        """Map vprism timeframe to akshare period parameter."""
        mapping = {
            TimeFrame.MINUTE_1: "1",
            TimeFrame.MINUTE_5: "5",
            TimeFrame.MINUTE_15: "15",
            TimeFrame.MINUTE_30: "30",
            TimeFrame.HOUR_1: "60",
            TimeFrame.DAY_1: "daily",
            TimeFrame.WEEK_1: "weekly",
            TimeFrame.MONTH_1: "monthly",
        }
        return mapping.get(timeframe, "daily")

    def standardize_dataframe(
        self, df: pd.DataFrame, symbol: str, asset_type: AssetType
    ) -> list[DataPoint]:
        """
        Convert akshare DataFrame to standardized DataPoint list.

        Args:
            df: Raw DataFrame from akshare
            symbol: Symbol identifier
            asset_type: Type of asset

        Returns:
            List of standardized DataPoint objects
        """
        if df is None or df.empty:
            return []

        data_points = []

        # Get appropriate column mapping
        asset_key = asset_type.value if asset_type else "stock"
        column_mapping = self._column_mappings.get(
            asset_key, self._column_mappings["stock"]
        )

        # Normalize column names
        df_normalized = df.copy()
        df_normalized.columns = [column_mapping.get(col, col) for col in df.columns]

        for _, row in df_normalized.iterrows():
            try:
                # Parse timestamp
                timestamp = self._parse_timestamp(row)
                if timestamp is None:
                    continue

                # Extract standardized data
                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=self._safe_decimal(row.get("open")),
                    high=self._safe_decimal(row.get("high")),
                    low=self._safe_decimal(row.get("low")),
                    close=self._safe_decimal(row.get("close")),
                    volume=self._safe_decimal(row.get("volume")),
                    amount=self._safe_decimal(row.get("amount")),
                    extra_fields=self._extract_extra_fields(row, column_mapping),
                )
                data_points.append(data_point)

            except Exception as e:
                logger.warning(f"Failed to parse row for symbol {symbol}: {e}")
                continue

        return data_points

    def _parse_timestamp(self, row: pd.Series) -> datetime | None:
        """Parse timestamp from row data."""
        timestamp = None

        if "timestamp" in row:
            timestamp_val = row["timestamp"]

            if isinstance(timestamp_val, str):
                # Try different date formats
                for fmt in [
                    "%Y-%m-%d",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d",
                    "%Y%m%d",
                    "%Y-%m-%d %H:%M",
                ]:
                    try:
                        timestamp = datetime.strptime(timestamp_val, fmt)
                        break
                    except ValueError:
                        continue
            elif isinstance(timestamp_val, pd.Timestamp):
                timestamp = timestamp_val.to_pydatetime()
            elif isinstance(timestamp_val, datetime):
                timestamp = timestamp_val

        return timestamp

    def _safe_decimal(self, value) -> Decimal | None:
        """Safely convert value to Decimal."""
        if pd.isna(value) or value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            return None

    def _extract_extra_fields(
        self, row: pd.Series, column_mapping: dict[str, str]
    ) -> dict[str, Any]:
        """Extract extra fields not in standard DataPoint."""
        standard_fields = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        }

        extra_fields = {}
        for col, value in row.items():
            if col not in standard_fields and not pd.isna(value):
                # Use original column name if it wasn't mapped
                original_col = None
                for orig, mapped in column_mapping.items():
                    if mapped == col:
                        original_col = orig
                        break

                # Store with original column name if available, otherwise use mapped name
                field_name = original_col if original_col else col
                extra_fields[field_name] = value

        return extra_fields

    async def fetch_data(self, query: DataQuery) -> pd.DataFrame:
        """
        Fetch data using appropriate akshare function.

        Args:
            query: Data query object

        Returns:
            Raw DataFrame from akshare

        Raises:
            ProviderException: If function not supported or fetch fails
        """
        function_config = self.get_akshare_function(query)
        if not function_config:
            raise ProviderException(
                "No akshare function available for query",
                provider="vprism_native",
                error_code="UNSUPPORTED_QUERY",
                details={"query": query.model_dump()},
            )

        function_name = function_config["function"]
        base_params = function_config["params"].copy()

        # Get akshare function
        if not AKSHARE_AVAILABLE:
            raise ProviderException(
                "akshare library is not available",
                provider="vprism_native",
                error_code="DEPENDENCY_MISSING",
            )

        if not hasattr(ak, function_name):
            raise ProviderException(
                f"Akshare function {function_name} not available",
                provider="vprism_native",
                error_code="FUNCTION_NOT_AVAILABLE",
            )

        akshare_func = getattr(ak, function_name)

        # Build parameters
        params = await self._build_function_params(query, base_params)

        try:
            # Execute akshare function
            logger.debug(f"Calling {function_name} with params: {params}")
            df = akshare_func(**params)

            if df is None or df.empty:
                logger.warning(f"No data returned from {function_name}")
                return pd.DataFrame()

            return df

        except Exception as e:
            logger.error(f"Error calling {function_name}: {e}")
            raise ProviderException(
                f"Failed to fetch data from akshare: {e!s}",
                provider="vprism_native",
                error_code="FETCH_ERROR",
                details={
                    "function": function_name,
                    "params": params,
                    "error_type": type(e).__name__,
                },
            ) from e

    async def _build_function_params(
        self, query: DataQuery, base_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Build parameters for akshare function call."""
        params = base_params.copy()

        # Add symbol if provided
        if query.symbols:
            # Most akshare functions take single symbol
            params["symbol"] = query.symbols[0]

        # Add timeframe for intraday data
        if query.timeframe and "{timeframe}" in str(params):
            timeframe_str = self.map_timeframe_to_akshare(query.timeframe)
            params = {
                k: v.format(timeframe=timeframe_str) if isinstance(v, str) else v
                for k, v in params.items()
            }

        # Add date range for historical data functions
        if query.start and any(
            keyword in str(params)
            for keyword in ["hist", "daily", "weekly", "monthly"]
        ):
            params["start_date"] = query.start.strftime("%Y%m%d")

        if query.end and any(
            keyword in str(params)
            for keyword in ["hist", "daily", "weekly", "monthly"]
        ):
            params["end_date"] = query.end.strftime("%Y%m%d")

        return params


class VPrismNativeProvider(EnhancedDataProvider):
    """
    VPrism Native Data Provider.

    A modern refactoring of akshare functionality that provides unified access
    to Chinese financial data through a composable API design. This provider
    serves as the primary data source for vprism with highest priority.
    """

    def __init__(self):
        """Initialize the VPrism native provider."""
        if not AKSHARE_AVAILABLE:
            raise ProviderException(
                "akshare library is required for VPrism native provider",
                provider="vprism_native",
                error_code="DEPENDENCY_MISSING",
            )

        # VPrism native doesn't require external authentication
        auth_config = AuthConfig(auth_type=AuthType.NONE)

        # Optimized rate limiting for native provider
        rate_limit = RateLimitConfig(
            requests_per_minute=60,  # Higher limit for native provider
            requests_per_hour=3000,
            concurrent_requests=5,  # Allow more concurrent requests
            backoff_factor=1.5,  # Faster recovery
            max_retries=5,  # More retries
        )

        super().__init__(
            provider_name="vprism_native",
            auth_config=auth_config,
            rate_limit=rate_limit,
        )

        self._adapter = AkshareModernAdapter()

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "vprism_native"

    def _discover_capability(self) -> ProviderCapability:
        """Discover and return provider capabilities."""
        return ProviderCapability(
            supported_assets={
                AssetType.STOCK,
                AssetType.BOND,
                AssetType.FUND,
                AssetType.ETF,
                AssetType.FUTURES,
                AssetType.INDEX,
                AssetType.CRYPTO,  # Limited support
            },
            supported_markets={
                MarketType.CN,  # Primary market
                MarketType.HK,  # Hong Kong stocks
                MarketType.US,  # Limited US data
            },
            supported_timeframes={
                TimeFrame.MINUTE_1,
                TimeFrame.MINUTE_5,
                TimeFrame.MINUTE_15,
                TimeFrame.MINUTE_30,
                TimeFrame.HOUR_1,
                TimeFrame.DAY_1,
                TimeFrame.WEEK_1,
                TimeFrame.MONTH_1,
            },
            max_symbols_per_request=10,  # Better batch support than raw akshare
            supports_real_time=False,  # Akshare has delays
            supports_historical=True,
            data_delay_seconds=300,  # 5-minute delay (better than akshare)
            max_history_days=7300,  # ~20 years of history
        )

    async def _authenticate(self) -> bool:
        """Perform authentication with the provider."""
        # VPrism native doesn't require authentication
        return True

    async def health_check(self) -> bool:
        """Check if the provider is healthy and available."""
        try:
            # Test with a simple query to check if akshare is working
            test_data = ak.stock_zh_a_spot_em()
            return test_data is not None and not test_data.empty
        except Exception as e:
            logger.warning(f"VPrism native health check failed: {e}")
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Retrieve data using the modern akshare adapter."""
        if not self.can_handle_query(query):
            raise ProviderException(
                "VPrism native provider cannot handle query",
                provider=self.name,
                error_code="UNSUPPORTED_QUERY",
                details={"query": query.model_dump()},
            )

        start_time = datetime.now()
        all_data_points = []

        try:
            # Handle multiple symbols with improved batching
            symbols = query.symbols or []
            if not symbols:
                # Get default symbols based on asset type
                symbols = await self._get_default_symbols(query)

            # Process symbols in batches for better performance
            batch_size = min(self.capability.max_symbols_per_request, len(symbols))

            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i : i + batch_size]

                for symbol in batch_symbols:
                    try:
                        # Create query for single symbol
                        symbol_query = query.model_copy()
                        symbol_query.symbols = [symbol]

                        # Fetch data using adapter
                        df = await self._adapter.fetch_data(symbol_query)

                        # Standardize data
                        symbol_data = self._adapter.standardize_dataframe(
                            df, symbol, query.asset
                        )
                        all_data_points.extend(symbol_data)

                        # Add small delay between requests to respect rate limits
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.warning(f"Failed to fetch data for symbol {symbol}: {e}")
                        continue

            # Sort data by timestamp and symbol
            all_data_points.sort(key=lambda x: (x.symbol, x.timestamp))

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Build response metadata
            metadata = ResponseMetadata(
                query_time=start_time,
                execution_time_ms=execution_time,
                record_count=len(all_data_points),
                cache_hit=False,
                warnings=[]
                if all_data_points
                else ["No data returned from vprism native"],
            )

            # Build provider info
            provider_info = ProviderInfo(
                name=self.name,
                version=f"vprism-native-1.0.0+akshare-{getattr(ak, '__version__', 'unknown')}",
                url="https://github.com/your-org/vprism",
                rate_limit=self.rate_limit.requests_per_minute,
                cost="free",
            )

            return DataResponse(
                data=all_data_points,
                metadata=metadata,
                source=provider_info,
                query=query,
            )

        except Exception as e:
            raise ProviderException(
                f"Error retrieving data from vprism native: {e!s}",
                provider=self.name,
                error_code="FETCH_ERROR",
                details={"error_type": type(e).__name__},
            ) from e

    async def _get_default_symbols(self, query: DataQuery) -> list[str]:
        """Get default symbols when none specified."""
        try:
            if query.asset == AssetType.STOCK and query.market == MarketType.CN:
                # Get top 20 A-share stocks
                stock_list = ak.stock_zh_a_spot_em()
                return stock_list["代码"].head(20).tolist()
            elif query.asset == AssetType.ETF and query.market == MarketType.CN:
                # Get top 10 ETFs
                etf_list = ak.fund_etf_spot_em()
                return etf_list["代码"].head(10).tolist()
            else:
                # Return empty list for unsupported combinations
                return []
        except Exception as e:
            logger.warning(f"Failed to get default symbols: {e}")
            return []

    async def stream_data(self, query: DataQuery) -> list[DataPoint]:
        """Stream data (not supported by akshare backend)."""
        raise ProviderException(
            "VPrism native provider does not support real-time streaming",
            provider=self.name,
            error_code="STREAMING_NOT_SUPPORTED",
        )

    def get_supported_functions(self) -> dict[str, str]:
        """Get list of supported akshare functions with descriptions."""
        return {
            key: config["description"]
            for key, config in self._adapter._function_mapping.items()
        }

    def get_function_mapping(self) -> dict[str, dict[str, Any]]:
        """Get complete function mapping for debugging/inspection."""
        return self._adapter._function_mapping.copy()
