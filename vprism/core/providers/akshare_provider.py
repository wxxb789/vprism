"""
Akshare data provider implementation.

This module provides a wrapper around the akshare library to integrate
it with the vprism platform. Used primarily for data validation and
compatibility testing with the original akshare functions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

from vprism.core.exceptions import ProviderException
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    ResponseMetadata,
    ProviderInfo,
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
    logger.warning("akshare not available - AkshareProvider will be disabled")


class AkshareProvider(EnhancedDataProvider):
    """
    Akshare data provider implementation.
    
    Provides access to Chinese financial data through the akshare library.
    This provider is primarily used for data validation and compatibility
    testing with the original akshare functions.
    """

    def __init__(self):
        """Initialize the akshare provider."""
        if not AKSHARE_AVAILABLE:
            raise ProviderException(
                "akshare library is not installed",
                provider="akshare",
                error_code="DEPENDENCY_MISSING"
            )

        # Akshare doesn't require authentication
        auth_config = AuthConfig(auth_type=AuthType.NONE)
        
        # Conservative rate limiting for akshare
        rate_limit = RateLimitConfig(
            requests_per_minute=30,  # Conservative limit
            requests_per_hour=1000,
            concurrent_requests=2,   # Limit concurrent requests
        )

        super().__init__(
            provider_name="akshare",
            auth_config=auth_config,
            rate_limit=rate_limit,
        )

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "akshare"

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
            },
            supported_markets={MarketType.CN},  # Primarily Chinese markets
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
            max_symbols_per_request=1,  # Akshare typically handles one symbol at a time
            supports_real_time=False,   # Akshare has data delays
            supports_historical=True,
            data_delay_seconds=900,     # 15-minute delay
            max_history_days=3650,      # ~10 years of history
        )

    async def _authenticate(self) -> bool:
        """Perform authentication with the provider."""
        # Akshare doesn't require authentication
        return True

    async def health_check(self) -> bool:
        """Check if the provider is healthy and available."""
        try:
            # Test with a simple query to check if akshare is working
            test_data = ak.stock_zh_a_spot_em()
            return test_data is not None and not test_data.empty
        except Exception as e:
            logger.warning(f"Akshare health check failed: {e}")
            return False

    def _map_timeframe_to_akshare(self, timeframe: TimeFrame) -> str:
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

    def _standardize_dataframe(self, df: pd.DataFrame, symbol: str) -> List[DataPoint]:
        """Convert akshare DataFrame to standardized DataPoint list."""
        data_points = []
        
        if df is None or df.empty:
            return data_points

        # Common column mappings for akshare data
        column_mappings = {
            # Date/time columns
            'date': 'timestamp',
            '日期': 'timestamp', 
            'datetime': 'timestamp',
            '时间': 'timestamp',
            
            # Price columns
            'open': 'open',
            '开盘': 'open',
            'high': 'high', 
            '最高': 'high',
            'low': 'low',
            '最低': 'low',
            'close': 'close',
            '收盘': 'close',
            
            # Volume columns
            'volume': 'volume',
            '成交量': 'volume',
            'amount': 'amount',
            '成交额': 'amount',
        }

        # Normalize column names
        df_normalized = df.copy()
        df_normalized.columns = [column_mappings.get(col, col) for col in df.columns]

        for _, row in df_normalized.iterrows():
            try:
                # Parse timestamp
                timestamp = None
                if 'timestamp' in row:
                    timestamp_val = row['timestamp']
                    if isinstance(timestamp_val, str):
                        # Try different date formats
                        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d']:
                            try:
                                timestamp = datetime.strptime(timestamp_val, fmt)
                                break
                            except ValueError:
                                continue
                    elif isinstance(timestamp_val, pd.Timestamp):
                        timestamp = timestamp_val.to_pydatetime()
                    elif isinstance(timestamp_val, datetime):
                        timestamp = timestamp_val

                if timestamp is None:
                    continue  # Skip rows without valid timestamp

                # Extract price data with safe conversion
                def safe_decimal(value) -> Optional[Decimal]:
                    if pd.isna(value) or value is None:
                        return None
                    try:
                        return Decimal(str(value))
                    except (ValueError, TypeError):
                        return None

                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=safe_decimal(row.get('open')),
                    high=safe_decimal(row.get('high')),
                    low=safe_decimal(row.get('low')),
                    close=safe_decimal(row.get('close')),
                    volume=safe_decimal(row.get('volume')),
                    amount=safe_decimal(row.get('amount')),
                    extra_fields={
                        k: v for k, v in row.items() 
                        if k not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'amount']
                        and not pd.isna(v)
                    }
                )
                data_points.append(data_point)

            except Exception as e:
                logger.warning(f"Failed to parse row for symbol {symbol}: {e}")
                continue

        return data_points

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Retrieve data using akshare functions."""
        if not self.can_handle_query(query):
            raise ProviderException(
                f"Akshare provider cannot handle query",
                provider=self.name,
                error_code="UNSUPPORTED_QUERY",
                details={"query": query.model_dump()}
            )

        start_time = datetime.now()
        all_data_points = []

        try:
            # Handle single symbol queries (akshare limitation)
            symbols = query.symbols or []
            if not symbols:
                # Get all stocks if no symbols specified
                if query.asset == AssetType.STOCK:
                    stock_list = ak.stock_zh_a_spot_em()
                    symbols = stock_list['代码'].head(10).tolist()  # Limit to first 10
                else:
                    raise ProviderException(
                        "No symbols specified and asset type not supported for listing",
                        provider=self.name,
                        error_code="MISSING_SYMBOLS"
                    )

            for symbol in symbols:
                try:
                    df = await self._fetch_symbol_data(symbol, query)
                    symbol_data = self._standardize_dataframe(df, symbol)
                    all_data_points.extend(symbol_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch data for symbol {symbol}: {e}")
                    continue

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Build response metadata
            metadata = ResponseMetadata(
                query_time=start_time,
                execution_time_ms=execution_time,
                record_count=len(all_data_points),
                cache_hit=False,
                warnings=[] if all_data_points else ["No data returned from akshare"]
            )

            # Build provider info
            provider_info = ProviderInfo(
                name=self.name,
                version=getattr(ak, '__version__', None),
                url="https://akshare.akfamily.xyz/",
                rate_limit=self.rate_limit.requests_per_minute,
                cost="free"
            )

            return DataResponse(
                data=all_data_points,
                metadata=metadata,
                source=provider_info,
                query=query,
            )

        except Exception as e:
            raise ProviderException(
                f"Error retrieving data from akshare: {str(e)}",
                provider=self.name,
                error_code="FETCH_ERROR",
                details={"error_type": type(e).__name__}
            )

    async def _fetch_symbol_data(self, symbol: str, query: DataQuery) -> pd.DataFrame:
        """Fetch data for a single symbol using appropriate akshare function."""
        try:
            if query.asset == AssetType.STOCK:
                if query.timeframe and query.timeframe != TimeFrame.DAY_1:
                    # Intraday data
                    period = self._map_timeframe_to_akshare(query.timeframe)
                    return ak.stock_zh_a_hist_min_em(
                        symbol=symbol,
                        period=period,
                        start_date=query.start.strftime('%Y-%m-%d') if query.start else None,
                        end_date=query.end.strftime('%Y-%m-%d') if query.end else None,
                    )
                else:
                    # Daily data
                    return ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=query.start.strftime('%Y%m%d') if query.start else None,
                        end_date=query.end.strftime('%Y%m%d') if query.end else None,
                    )
            elif query.asset == AssetType.ETF:
                return ak.fund_etf_hist_em(
                    symbol=symbol,
                    period="daily",
                    start_date=query.start.strftime('%Y%m%d') if query.start else None,
                    end_date=query.end.strftime('%Y%m%d') if query.end else None,
                )
            elif query.asset == AssetType.FUND:
                return ak.fund_open_fund_info_em(
                    fund=symbol,
                    indicator="累计净值走势"
                )
            else:
                raise ProviderException(
                    f"Asset type {query.asset} not supported by akshare provider",
                    provider=self.name,
                    error_code="UNSUPPORTED_ASSET"
                )

        except Exception as e:
            logger.error(f"Akshare fetch error for {symbol}: {e}")
            raise

    async def stream_data(self, query: DataQuery) -> List[DataPoint]:
        """Stream data (akshare doesn't support real-time streaming)."""
        raise ProviderException(
            "Akshare provider does not support real-time streaming",
            provider=self.name,
            error_code="STREAMING_NOT_SUPPORTED"
        )