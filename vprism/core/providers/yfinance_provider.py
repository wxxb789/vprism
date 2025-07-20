"""
Yahoo Finance (yfinance) data provider implementation.

This module provides integration with the yfinance library to access
Yahoo Finance data for global markets, particularly US stocks and ETFs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from collections.abc import AsyncIterator

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

# Optional import for yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available - YfinanceProvider will be disabled")


class YfinanceProvider(EnhancedDataProvider):
    """
    Yahoo Finance data provider implementation.
    
    Provides access to global financial data through the yfinance library,
    with support for stocks, ETFs, indices, and cryptocurrencies.
    """

    def __init__(self):
        """Initialize the yfinance provider."""
        if not YFINANCE_AVAILABLE:
            raise ProviderException(
                "yfinance library is not installed",
                provider="yfinance",
                error_code="DEPENDENCY_MISSING"
            )

        # Yahoo Finance doesn't require authentication
        auth_config = AuthConfig(auth_type=AuthType.NONE)
        
        # Reasonable rate limiting for Yahoo Finance
        rate_limit = RateLimitConfig(
            requests_per_minute=60,   # Yahoo Finance is quite permissive
            requests_per_hour=2000,
            concurrent_requests=5,
        )

        super().__init__(
            provider_name="yfinance",
            auth_config=auth_config,
            rate_limit=rate_limit,
        )

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "yfinance"

    def _discover_capability(self) -> ProviderCapability:
        """Discover and return provider capabilities."""
        return ProviderCapability(
            supported_assets={
                AssetType.STOCK,
                AssetType.ETF,
                AssetType.INDEX,
                AssetType.CRYPTO,
                AssetType.FOREX,
                AssetType.FUTURES,
                AssetType.OPTIONS,
            },
            supported_markets={
                MarketType.US,
                MarketType.GLOBAL,
                MarketType.EU,
                MarketType.JP,
                MarketType.HK,
                MarketType.AU,
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
                TimeFrame.QUARTER_1,
                TimeFrame.YEAR_1,
            },
            max_symbols_per_request=100,  # yfinance can handle multiple symbols
            supports_real_time=True,      # Near real-time data
            supports_historical=True,
            data_delay_seconds=0,         # Real-time for most markets
            max_history_days=36500,       # ~100 years of history available
        )

    async def _authenticate(self) -> bool:
        """Perform authentication with the provider."""
        # Yahoo Finance doesn't require authentication
        return True

    async def health_check(self) -> bool:
        """Check if the provider is healthy and available."""
        try:
            # Test with a simple query for a well-known symbol
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            return info is not None and 'symbol' in info
        except Exception as e:
            logger.warning(f"Yahoo Finance health check failed: {e}")
            return False

    def _map_timeframe_to_yfinance(self, timeframe: TimeFrame) -> str:
        """Map vprism timeframe to yfinance interval parameter."""
        mapping = {
            TimeFrame.MINUTE_1: "1m",
            TimeFrame.MINUTE_5: "5m",
            TimeFrame.MINUTE_15: "15m",
            TimeFrame.MINUTE_30: "30m",
            TimeFrame.HOUR_1: "1h",
            TimeFrame.DAY_1: "1d",
            TimeFrame.WEEK_1: "1wk",
            TimeFrame.MONTH_1: "1mo",
            TimeFrame.QUARTER_1: "3mo",
            TimeFrame.YEAR_1: "1y",
        }
        return mapping.get(timeframe, "1d")

    def _standardize_dataframe(self, df: pd.DataFrame, symbol: str) -> List[DataPoint]:
        """Convert yfinance DataFrame to standardized DataPoint list."""
        data_points = []
        
        if df is None or df.empty:
            return data_points

        # yfinance typically returns data with standard column names
        for timestamp, row in df.iterrows():
            try:
                # Handle timestamp
                if isinstance(timestamp, pd.Timestamp):
                    dt = timestamp.to_pydatetime()
                else:
                    dt = pd.to_datetime(timestamp).to_pydatetime()

                # Safe decimal conversion
                def safe_decimal(value) -> Optional[Decimal]:
                    if pd.isna(value) or value is None:
                        return None
                    try:
                        return Decimal(str(value))
                    except (ValueError, TypeError):
                        return None

                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=dt,
                    open=safe_decimal(row.get('Open')),
                    high=safe_decimal(row.get('High')),
                    low=safe_decimal(row.get('Low')),
                    close=safe_decimal(row.get('Close')),
                    volume=safe_decimal(row.get('Volume')),
                    amount=None,  # Yahoo Finance doesn't provide amount directly
                    extra_fields={
                        'adj_close': str(row.get('Adj Close')) if not pd.isna(row.get('Adj Close')) else None,
                        'dividends': str(row.get('Dividends')) if not pd.isna(row.get('Dividends')) else None,
                        'stock_splits': str(row.get('Stock Splits')) if not pd.isna(row.get('Stock Splits')) else None,
                    }
                )
                data_points.append(data_point)

            except Exception as e:
                logger.warning(f"Failed to parse row for symbol {symbol}: {e}")
                continue

        return data_points

    async def get_data(self, query: DataQuery) -> DataResponse:
        """Retrieve data using yfinance."""
        if not self.can_handle_query(query):
            raise ProviderException(
                f"Yahoo Finance provider cannot handle query",
                provider=self.name,
                error_code="UNSUPPORTED_QUERY",
                details={"query": query.model_dump()}
            )

        start_time = datetime.now()
        all_data_points = []

        try:
            symbols = query.symbols or []
            if not symbols:
                raise ProviderException(
                    "Yahoo Finance requires specific symbols",
                    provider=self.name,
                    error_code="MISSING_SYMBOLS"
                )

            # Determine the interval
            interval = self._map_timeframe_to_yfinance(query.timeframe or TimeFrame.DAY_1)
            
            # Handle date range
            start_date = query.start
            end_date = query.end or datetime.now()
            
            # Adjust for intraday data limitations
            if interval in ['1m', '2m', '5m', '15m', '30m', '1h']:
                # Yahoo Finance limits intraday data to last 60 days
                max_start = datetime.now() - timedelta(days=60)
                if start_date and start_date < max_start:
                    start_date = max_start
                    logger.warning(f"Adjusted start date to {start_date} for intraday data")

            # Fetch data for all symbols at once (yfinance supports this)
            try:
                if len(symbols) == 1:
                    # Single symbol
                    ticker = yf.Ticker(symbols[0])
                    df = ticker.history(
                        start=start_date,
                        end=end_date,
                        interval=interval,
                        auto_adjust=True,
                        prepost=True,
                        threads=True
                    )
                    if not df.empty:
                        symbol_data = self._standardize_dataframe(df, symbols[0])
                        all_data_points.extend(symbol_data)
                    else:
                        logger.warning(f"No data returned for symbol {symbols[0]}")
                else:
                    # Multiple symbols - use batch download for efficiency
                    try:
                        # Try batch download first
                        data = yf.download(
                            tickers=' '.join(symbols),
                            start=start_date,
                            end=end_date,
                            interval=interval,
                            auto_adjust=True,
                            prepost=True,
                            threads=True,
                            group_by='ticker'
                        )
                        
                        if not data.empty:
                            # Handle multi-symbol response
                            if len(symbols) == 1:
                                # Single symbol in batch
                                symbol_data = self._standardize_dataframe(data, symbols[0])
                                all_data_points.extend(symbol_data)
                            else:
                                # Multiple symbols
                                for symbol in symbols:
                                    if symbol in data.columns.levels[0]:
                                        symbol_df = data[symbol].dropna()
                                        if not symbol_df.empty:
                                            symbol_data = self._standardize_dataframe(symbol_df, symbol)
                                            all_data_points.extend(symbol_data)
                    except Exception as batch_error:
                        logger.warning(f"Batch download failed: {batch_error}, falling back to individual requests")
                        
                        # Fallback to individual requests
                        for symbol in symbols:
                            try:
                                ticker = yf.Ticker(symbol)
                                df = ticker.history(
                                    start=start_date,
                                    end=end_date,
                                    interval=interval,
                                    auto_adjust=True,
                                    prepost=True,
                                    threads=True
                                )
                                if not df.empty:
                                    symbol_data = self._standardize_dataframe(df, symbol)
                                    all_data_points.extend(symbol_data)
                                else:
                                    logger.warning(f"No data returned for symbol {symbol}")
                            except Exception as e:
                                logger.warning(f"Failed to fetch data for symbol {symbol}: {e}")
                                continue

            except Exception as e:
                logger.error(f"Yahoo Finance fetch error: {e}")
                raise ProviderException(
                    f"Failed to fetch data from Yahoo Finance: {str(e)}",
                    provider=self.name,
                    error_code="FETCH_ERROR",
                    details={"error_type": type(e).__name__}
                )

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Build response metadata
            metadata = ResponseMetadata(
                query_time=start_time,
                execution_time_ms=execution_time,
                record_count=len(all_data_points),
                cache_hit=False,
                warnings=[] if all_data_points else ["No data returned from Yahoo Finance"]
            )

            # Build provider info
            provider_info = ProviderInfo(
                name=self.name,
                version=getattr(yf, '__version__', None),
                url="https://finance.yahoo.com/",
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
                f"Error retrieving data from Yahoo Finance: {str(e)}",
                provider=self.name,
                error_code="FETCH_ERROR",
                details={"error_type": type(e).__name__}
            )

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """Stream real-time data (polling-based implementation)."""
        if not self.capability.supports_real_time:
            raise ProviderException(
                "Yahoo Finance provider does not support real-time streaming",
                provider=self.name,
                error_code="STREAMING_NOT_SUPPORTED"
            )

        symbols = query.symbols or []
        if not symbols:
            raise ProviderException(
                "Symbols required for streaming",
                provider=self.name,
                error_code="MISSING_SYMBOLS"
            )

        # Simple polling-based streaming
        import asyncio
        
        last_timestamps = {}  # Track last timestamp for each symbol
        
        while True:
            try:
                # Create a modified query for current data
                current_query = DataQuery(
                    asset=query.asset,
                    market=query.market,
                    symbols=symbols,
                    timeframe=TimeFrame.MINUTE_1,  # Use 1-minute data for streaming
                )
                
                response = await self.get_data(current_query)
                
                # Yield only new data points
                for data_point in response.data:
                    symbol = data_point.symbol
                    timestamp = data_point.timestamp
                    
                    # Check if this is a new data point
                    if symbol not in last_timestamps or timestamp > last_timestamps[symbol]:
                        last_timestamps[symbol] = timestamp
                        yield data_point
                
                # Wait before next poll (1 minute for Yahoo Finance)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Streaming error from Yahoo Finance: {e}")
                # Don't break immediately, try to recover
                await asyncio.sleep(30)  # Wait 30 seconds before retry
                continue

    def get_asset_info(self, symbol: str) -> Dict[str, Any]:
        """Get detailed asset information from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol,
                'name': info.get('longName', info.get('shortName', symbol)),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'country': info.get('country'),
                'currency': info.get('currency'),
                'exchange': info.get('exchange'),
                'market_cap': info.get('marketCap'),
                'website': info.get('website'),
                'description': info.get('longBusinessSummary'),
                'employees': info.get('fullTimeEmployees'),
            }
        except Exception as e:
            logger.warning(f"Failed to get asset info for {symbol}: {e}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_quote(self, symbol: str) -> Optional[DataPoint]:
        """Get real-time quote for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get current data
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                latest = hist.iloc[-1]
                return DataPoint(
                    symbol=symbol,
                    timestamp=hist.index[-1].to_pydatetime(),
                    open=Decimal(str(latest['Open'])) if not pd.isna(latest['Open']) else None,
                    high=Decimal(str(latest['High'])) if not pd.isna(latest['High']) else None,
                    low=Decimal(str(latest['Low'])) if not pd.isna(latest['Low']) else None,
                    close=Decimal(str(latest['Close'])) if not pd.isna(latest['Close']) else None,
                    volume=Decimal(str(latest['Volume'])) if not pd.isna(latest['Volume']) else None,
                )
                
        except Exception as e:
            logger.warning(f"Failed to get quote for {symbol}: {e}")
            return None

    def get_options_chain(self, symbol: str) -> Dict[str, Any]:
        """Get options chain for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            options = ticker.options
            
            if not options:
                return {'symbol': symbol, 'options': []}
            
            # Get the nearest expiration
            nearest_exp = options[0]
            option_chain = ticker.option_chain(nearest_exp)
            
            return {
                'symbol': symbol,
                'expiration_dates': list(options),
                'nearest_expiration': nearest_exp,
                'calls': option_chain.calls.to_dict('records') if hasattr(option_chain, 'calls') else [],
                'puts': option_chain.puts.to_dict('records') if hasattr(option_chain, 'puts') else []
            }
            
        except Exception as e:
            logger.warning(f"Failed to get options chain for {symbol}: {e}")
            return {'symbol': symbol, 'error': str(e)}

    def get_dividends(self, symbol: str) -> List[Dict[str, Any]]:
        """Get dividend history for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            dividends = ticker.dividends
            
            if dividends.empty:
                return []
            
            return [
                {
                    'date': date.strftime('%Y-%m-%d'),
                    'dividend': float(amount)
                }
                for date, amount in dividends.items()
            ]
            
        except Exception as e:
            logger.warning(f"Failed to get dividends for {symbol}: {e}")
            return []