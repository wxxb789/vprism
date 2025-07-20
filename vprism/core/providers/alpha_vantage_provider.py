"""
Alpha Vantage data provider implementation.

This module provides integration with the Alpha Vantage API to access
financial data including stocks, forex, and cryptocurrencies with
real-time and historical data support.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from collections.abc import AsyncIterator

import httpx

from vprism.core.http_adapter import HttpConfig, HttpDataProvider, RetryConfig
from vprism.core.exceptions import ProviderException, AuthenticationException
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    AuthConfig,
    AuthType,
    ProviderCapability,
    RateLimitConfig,
)

logger = logging.getLogger(__name__)


class AlphaVantageProvider(HttpDataProvider):
    """
    Alpha Vantage data provider implementation.
    
    Provides access to financial data through the Alpha Vantage API,
    supporting stocks, forex, and cryptocurrencies with both real-time
    and historical data.
    """

    def __init__(self, api_key: str):
        """Initialize the Alpha Vantage provider."""
        if not api_key:
            raise ProviderException(
                "Alpha Vantage API key is required",
                provider="alpha_vantage",
                error_code="MISSING_API_KEY"
            )

        # Configure HTTP settings
        http_config = HttpConfig(
            base_url="https://www.alphavantage.co/query",
            timeout=30.0,
            user_agent="vprism-alpha-vantage/1.0.0",
        )

        # Configure authentication
        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credentials={"api_key": api_key}
        )

        # Alpha Vantage has strict rate limits
        rate_limit = RateLimitConfig(
            requests_per_minute=5,    # Free tier: 5 requests per minute
            requests_per_hour=500,    # Free tier: 500 requests per day
            concurrent_requests=1,    # Sequential requests only
        )

        # Configure retry behavior
        retry_config = RetryConfig(
            max_retries=3,
            backoff_factor=2.0,
        )

        super().__init__(
            provider_name="alpha_vantage",
            http_config=http_config,
            auth_config=auth_config,
            rate_limit=rate_limit,
            retry_config=retry_config,
        )

        self.api_key = api_key

    @property
    def name(self) -> str:
        """Provider name identifier."""
        return "alpha_vantage"

    def _discover_capability(self) -> ProviderCapability:
        """Discover and return provider capabilities."""
        return ProviderCapability(
            supported_assets={
                AssetType.STOCK,
                AssetType.ETF,
                AssetType.FOREX,
                AssetType.CRYPTO,
                AssetType.INDEX,
            },
            supported_markets={
                MarketType.US,
                MarketType.GLOBAL,
                MarketType.EU,
                MarketType.JP,
                MarketType.HK,
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
            max_symbols_per_request=1,  # Alpha Vantage handles one symbol at a time
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,       # Real-time data
            max_history_days=7300,      # ~20 years of history
        )

    def _build_request_url(self, query: DataQuery) -> str:
        """Build request URL for the given query."""
        # Alpha Vantage uses query parameters, so base URL is sufficient
        return ""

    def _build_request_params(self, query: DataQuery) -> Dict[str, Any]:
        """Build request parameters for the given query."""
        params = {
            "apikey": self.api_key,
        }

        # Determine function based on asset type and timeframe
        if query.asset == AssetType.STOCK or query.asset == AssetType.ETF:
            if query.timeframe and query.timeframe != TimeFrame.DAY_1:
                # Intraday data
                params["function"] = "TIME_SERIES_INTRADAY"
                params["interval"] = self._map_timeframe_to_alpha_vantage(query.timeframe)
            else:
                # Daily data
                params["function"] = "TIME_SERIES_DAILY"
            
            # Add symbol
            if query.symbols:
                params["symbol"] = query.symbols[0]  # Alpha Vantage handles one symbol at a time
                
        elif query.asset == AssetType.FOREX:
            params["function"] = "FX_INTRADAY" if query.timeframe != TimeFrame.DAY_1 else "FX_DAILY"
            if query.symbols:
                # Assume forex pair format like "EURUSD"
                symbol = query.symbols[0]
                if len(symbol) == 6:
                    params["from_symbol"] = symbol[:3]
                    params["to_symbol"] = symbol[3:]
                    
        elif query.asset == AssetType.CRYPTO:
            params["function"] = "DIGITAL_CURRENCY_DAILY"
            if query.symbols:
                params["symbol"] = query.symbols[0]
                params["market"] = "USD"  # Default to USD market

        # Add output size
        params["outputsize"] = "full" if query.start or query.end else "compact"

        return params

    def _map_timeframe_to_alpha_vantage(self, timeframe: TimeFrame) -> str:
        """Map vprism timeframe to Alpha Vantage interval parameter."""
        mapping = {
            TimeFrame.MINUTE_1: "1min",
            TimeFrame.MINUTE_5: "5min",
            TimeFrame.MINUTE_15: "15min",
            TimeFrame.MINUTE_30: "30min",
            TimeFrame.HOUR_1: "60min",
        }
        return mapping.get(timeframe, "1min")

    async def _parse_response(
        self, response: httpx.Response, query: DataQuery
    ) -> List[DataPoint]:
        """Parse Alpha Vantage JSON response into data points."""
        try:
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data:
                raise ProviderException(
                    f"Alpha Vantage API error: {data['Error Message']}",
                    provider=self.name,
                    error_code="API_ERROR"
                )
            
            if "Note" in data:
                raise ProviderException(
                    f"Alpha Vantage rate limit: {data['Note']}",
                    provider=self.name,
                    error_code="RATE_LIMIT_EXCEEDED"
                )

            data_points = []
            symbol = query.symbols[0] if query.symbols else "UNKNOWN"

            # Parse different response formats
            if query.asset in [AssetType.STOCK, AssetType.ETF]:
                time_series_key = self._get_time_series_key(data, query)
                if time_series_key and time_series_key in data:
                    time_series = data[time_series_key]
                    data_points = self._parse_stock_data(time_series, symbol, query)
                    
            elif query.asset == AssetType.FOREX:
                time_series_key = self._get_forex_time_series_key(data, query)
                if time_series_key and time_series_key in data:
                    time_series = data[time_series_key]
                    data_points = self._parse_forex_data(time_series, symbol, query)
                    
            elif query.asset == AssetType.CRYPTO:
                if "Time Series (Digital Currency Daily)" in data:
                    time_series = data["Time Series (Digital Currency Daily)"]
                    data_points = self._parse_crypto_data(time_series, symbol, query)

            # Filter by date range if specified
            if query.start or query.end:
                data_points = self._filter_by_date_range(data_points, query.start, query.end)

            return data_points

        except Exception as e:
            if isinstance(e, ProviderException):
                raise
            raise ProviderException(
                f"Failed to parse Alpha Vantage response: {str(e)}",
                provider=self.name,
                error_code="PARSE_ERROR",
                details={"error_type": type(e).__name__}
            )

    def _get_time_series_key(self, data: Dict[str, Any], query: DataQuery) -> Optional[str]:
        """Get the appropriate time series key from the response."""
        possible_keys = [
            "Time Series (Intraday)",
            "Time Series (Daily)",
            "Weekly Time Series",
            "Monthly Time Series",
        ]
        
        for key in possible_keys:
            if key in data:
                return key
        return None

    def _get_forex_time_series_key(self, data: Dict[str, Any], query: DataQuery) -> Optional[str]:
        """Get the appropriate forex time series key from the response."""
        possible_keys = [
            "Time Series FX (Intraday)",
            "Time Series FX (Daily)",
        ]
        
        for key in possible_keys:
            if key in data:
                return key
        return None

    def _parse_stock_data(self, time_series: Dict[str, Any], symbol: str, query: DataQuery) -> List[DataPoint]:
        """Parse stock/ETF time series data."""
        data_points = []
        
        for timestamp_str, values in time_series.items():
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d")
                except ValueError:
                    continue

            def safe_decimal(key: str) -> Optional[Decimal]:
                value = values.get(key)
                if value is None:
                    return None
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError):
                    return None

            data_point = DataPoint(
                symbol=symbol,
                timestamp=timestamp,
                open=safe_decimal("1. open"),
                high=safe_decimal("2. high"),
                low=safe_decimal("3. low"),
                close=safe_decimal("4. close"),
                volume=safe_decimal("5. volume"),
                amount=None,
                extra_fields={}
            )
            data_points.append(data_point)

        return sorted(data_points, key=lambda x: x.timestamp)

    def _parse_forex_data(self, time_series: Dict[str, Any], symbol: str, query: DataQuery) -> List[DataPoint]:
        """Parse forex time series data."""
        data_points = []
        
        for timestamp_str, values in time_series.items():
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d")
                except ValueError:
                    continue

            def safe_decimal(key: str) -> Optional[Decimal]:
                value = values.get(key)
                if value is None:
                    return None
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError):
                    return None

            data_point = DataPoint(
                symbol=symbol,
                timestamp=timestamp,
                open=safe_decimal("1. open"),
                high=safe_decimal("2. high"),
                low=safe_decimal("3. low"),
                close=safe_decimal("4. close"),
                volume=None,  # Forex doesn't have volume
                amount=None,
                extra_fields={}
            )
            data_points.append(data_point)

        return sorted(data_points, key=lambda x: x.timestamp)

    def _parse_crypto_data(self, time_series: Dict[str, Any], symbol: str, query: DataQuery) -> List[DataPoint]:
        """Parse cryptocurrency time series data."""
        data_points = []
        
        for timestamp_str, values in time_series.items():
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d")
            except ValueError:
                continue

            def safe_decimal(key: str) -> Optional[Decimal]:
                value = values.get(key)
                if value is None:
                    return None
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError):
                    return None

            data_point = DataPoint(
                symbol=symbol,
                timestamp=timestamp,
                open=safe_decimal("1a. open (USD)"),
                high=safe_decimal("2a. high (USD)"),
                low=safe_decimal("3a. low (USD)"),
                close=safe_decimal("4a. close (USD)"),
                volume=safe_decimal("5. volume"),
                amount=safe_decimal("6. market cap (USD)"),
                extra_fields={}
            )
            data_points.append(data_point)

        return sorted(data_points, key=lambda x: x.timestamp)

    def _filter_by_date_range(
        self, 
        data_points: List[DataPoint], 
        start: Optional[datetime], 
        end: Optional[datetime]
    ) -> List[DataPoint]:
        """Filter data points by date range."""
        if not start and not end:
            return data_points

        filtered = []
        for point in data_points:
            if start and point.timestamp < start:
                continue
            if end and point.timestamp > end:
                continue
            filtered.append(point)

        return filtered

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """Stream real-time data (polling-based implementation)."""
        if not self.capability.supports_real_time:
            raise ProviderException(
                "Alpha Vantage provider does not support real-time streaming",
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

        # Alpha Vantage rate limits are strict, so we use longer polling intervals
        while True:
            try:
                # Create a modified query for current data
                current_query = DataQuery(
                    asset=query.asset,
                    market=query.market,
                    symbols=[symbols[0]],  # One symbol at a time
                    timeframe=TimeFrame.MINUTE_1,
                    limit=1
                )
                
                response = await self.get_data(current_query)
                
                # Yield the latest data points
                for data_point in response.data[-1:]:  # Only the latest point
                    yield data_point
                
                # Wait before next poll (12 seconds to respect rate limits)
                await asyncio.sleep(12)
                
            except Exception as e:
                logger.error(f"Streaming error from Alpha Vantage: {e}")
                break