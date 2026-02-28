"""Alpha Vantage data provider implementation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from loguru import logger

from vprism.core.data.providers.base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from vprism.core.exceptions.base import ProviderError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from vprism.core.models.query import DataQuery

# Mapping from TimeFrame to interval parameter for intraday requests
_INTERVAL_MAP: dict[TimeFrame, str] = {
    TimeFrame.MINUTE_1: "1min",
    TimeFrame.MINUTE_5: "5min",
    TimeFrame.MINUTE_15: "15min",
    TimeFrame.MINUTE_30: "30min",
    TimeFrame.HOUR_1: "60min",
}

# Intraday timeframes share the same API function prefix pattern
_INTRADAY_TIMEFRAMES = frozenset(_INTERVAL_MAP.keys())


def _api_function(prefix: str, timeframe: TimeFrame) -> str:
    """Resolve the AlphaVantage API function name."""
    if timeframe in _INTRADAY_TIMEFRAMES:
        return f"{prefix}_INTRADAY" if prefix != "TIME_SERIES" else "TIME_SERIES_INTRADAY"
    suffix_map = {TimeFrame.DAY_1: "DAILY", TimeFrame.WEEK_1: "WEEKLY", TimeFrame.MONTH_1: "MONTHLY"}
    suffix = suffix_map.get(timeframe, "DAILY")
    return f"{prefix}_{suffix}"


class AlphaVantage(DataProvider):
    """Alpha Vantage data provider."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str) -> None:
        auth_config = AuthConfig(auth_type=AuthType.API_KEY, credentials={"api_key": api_key}, required_fields=["api_key"])
        rate_limit = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=300,
            requests_per_day=500,
            concurrent_requests=1,
            backoff_factor=2.0,
            max_retries=3,
            initial_delay=1.0,
        )
        super().__init__("alpha_vantage", auth_config, rate_limit)
        self.api_key = api_key

    def _discover_capability(self) -> ProviderCapability:
        return ProviderCapability(
            supported_assets={"stock", "etf", "index", "forex", "crypto"},
            supported_markets={"us", "global"},
            supported_timeframes={"1min", "5min", "15min", "30min", "60min", "1d", "1wk", "1mo"},
            max_symbols_per_request=1,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
            rate_limits={"requests_per_minute": 5, "requests_per_hour": 300, "requests_per_day": 500},
        )

    async def authenticate(self) -> bool:
        if not self.api_key:
            return False
        try:
            import aiohttp

            url = f"{self.BASE_URL}?function=SYMBOL_SEARCH&keywords=IBM&apikey={self.api_key}"
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                data = await response.json()
                if "Error Message" in data:
                    return False
                self._is_authenticated = True
                return True
        except Exception:
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        if not self.can_handle_query(query):
            raise ProviderError(f"AlphaVantage cannot handle query: {query}", "AlphaVantage")
        if not self.is_authenticated:
            await self.authenticate()
            if not self.is_authenticated:
                raise ProviderError("AlphaVantage authentication failed", "AlphaVantage")
        try:
            data_points = await self._fetch_data(query)
            return DataResponse(
                data=data_points,
                metadata=ResponseMetadata(total_records=len(data_points), query_time_ms=0.0, data_source="alpha_vantage", cache_hit=False),
                source=ProviderInfo(name="alpha_vantage", endpoint=self.BASE_URL),
                cached=False,
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to fetch data from AlphaVantage: {e}", "AlphaVantage") from e

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        data_response = await self.get_data(query)
        for dp in data_response.data:
            yield dp

    # ------------------------------------------------------------------ #
    # Internal fetch logic (unified for stock / forex / crypto)
    # ------------------------------------------------------------------ #

    async def _fetch_data(self, query: DataQuery) -> list[DataPoint]:
        if not query.symbols:
            return []
        data_points: list[DataPoint] = []
        for symbol in query.symbols:
            try:
                data_points.extend(await self._fetch_symbol_data(symbol, query))
            except Exception as e:
                logger.warning(f"Error fetching data for {symbol}: {e}")
        return data_points

    async def _fetch_symbol_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """Build params per asset type, then call the unified _request()."""
        timeframe = query.timeframe or TimeFrame.DAY_1
        market = query.market or "us"

        if query.asset == AssetType.FOREX:
            from_cur, to_cur = symbol[:3], symbol[3:]
            prefix = "FX"
            function = _api_function(prefix, timeframe)
            params: dict[str, str] = {"function": function, "from_symbol": from_cur, "to_symbol": to_cur, "apikey": self.api_key}
            if timeframe in _INTRADAY_TIMEFRAMES:
                params["interval"] = _INTERVAL_MAP[timeframe]
            market = "global"

        elif query.asset == AssetType.CRYPTO:
            function = _api_function("CRYPTO", timeframe)
            # Daily/weekly/monthly crypto uses DIGITAL_CURRENCY_ prefix
            if timeframe not in _INTRADAY_TIMEFRAMES:
                dc_suffix = {TimeFrame.DAY_1: "DAILY", TimeFrame.WEEK_1: "WEEKLY", TimeFrame.MONTH_1: "MONTHLY"}
                function = f"DIGITAL_CURRENCY_{dc_suffix.get(timeframe, 'DAILY')}"
            params = {"function": function, "symbol": symbol, "market": "USD", "apikey": self.api_key}
            if timeframe in _INTRADAY_TIMEFRAMES:
                params["interval"] = _INTERVAL_MAP[timeframe]
            market = "USD"

        else:  # stock / etf / index / default
            prefix = "TIME_SERIES"
            function = _api_function(prefix, timeframe)
            params = {"function": function, "symbol": symbol, "apikey": self.api_key, "outputsize": "full"}
            if timeframe in _INTRADAY_TIMEFRAMES:
                params["interval"] = _INTERVAL_MAP[timeframe]

        data = await self._request(params)
        return self._parse_time_series(data, symbol, market)

    async def _request(self, params: dict[str, str]) -> dict[str, Any]:
        """Execute a single AlphaVantage API request."""
        import aiohttp

        async with aiohttp.ClientSession() as session, session.get(self.BASE_URL, params=params) as response:
            data: dict[str, Any] = await response.json()

        if "Error Message" in data:
            raise ProviderError(f"AlphaVantage API error: {data['Error Message']}", "AlphaVantage")
        if "Note" in data:
            raise ProviderError(f"AlphaVantage rate limit: {data['Note']}", "AlphaVantage")
        return data

    def _parse_time_series(self, data: dict[str, Any], symbol: str, market: str) -> list[DataPoint]:
        """Parse any AlphaVantage time-series response into DataPoints."""
        # Find the time-series key (varies by endpoint)
        ts_key = next((k for k in data if k.startswith("Time Series") or k.startswith("Weekly") or k.startswith("Monthly")), None)
        if not ts_key:
            return []

        points: list[DataPoint] = []
        for date_str, values in data[ts_key].items():
            try:
                fmt = "%Y-%m-%d %H:%M:%S" if " " in date_str else "%Y-%m-%d"
                timestamp = datetime.strptime(date_str, fmt)

                open_price = Decimal(str(values.get("1. open", 0)))
                high_price = Decimal(str(values.get("2. high", 0)))
                low_price = Decimal(str(values.get("3. low", 0)))
                close_price = Decimal(str(values.get("4. close", 0)))
                volume = Decimal(str(values.get("5. volume", 0)))

                points.append(
                    DataPoint(
                        symbol=symbol,
                        timestamp=timestamp,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        volume=volume,
                        amount=close_price * volume,
                        market=MarketType(market),
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing AlphaVantage data: {e}")
        points.sort(key=lambda x: x.timestamp)
        return points

    async def health_check(self) -> bool:
        return await self.authenticate()
