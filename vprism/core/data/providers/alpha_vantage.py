"""Alpha Vantage数据提供商实现."""

from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import aiohttp

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
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata


class AlphaVantage(DataProvider):
    """Alpha Vantage数据提供商实现."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str) -> None:
        """初始化AlphaVantage提供商."""
        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credentials={"api_key": api_key},
            required_fields=["api_key"],
        )

        rate_limit = RateLimitConfig(
            requests_per_minute=5,  # 免费版限制
            requests_per_hour=300,
            requests_per_day=500,
            concurrent_requests=1,
            backoff_factor=2.0,
            max_retries=3,
            initial_delay=1.0,
        )

        super().__init__("alpha_vantage", auth_config, rate_limit)
        self.api_key = api_key
        self.client: Any = None  # 客户端将在认证时初始化

    def _discover_capability(self) -> ProviderCapability:
        """发现AlphaVantage能力."""
        return ProviderCapability(
            supported_assets={"stock", "etf", "index", "forex", "crypto"},
            supported_markets={"us", "global"},
            supported_timeframes={
                "1min",
                "5min",
                "15min",
                "30min",
                "60min",
                "1d",
                "1wk",
                "1mo",
            },
            max_symbols_per_request=1,  # AlphaVantage每次只能请求一个符号
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
            rate_limits={
                "requests_per_minute": 5,
                "requests_per_hour": 300,
                "requests_per_day": 500,
            },
        )

    async def authenticate(self) -> bool:
        """验证API密钥."""
        if not self.api_key:
            return False

        try:
            # 测试API密钥是否有效
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
        """获取数据."""
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
                metadata=ResponseMetadata(
                    total_records=len(data_points),
                    query_time_ms=0.0,
                    data_source="alpha_vantage",
                    cache_hit=False,
                ),
                source=ProviderInfo(name="alpha_vantage", endpoint=self.BASE_URL),
                cached=False,
            )

        except Exception as e:
            raise ProviderError(f"Failed to fetch data from AlphaVantage: {e}", "AlphaVantage") from e

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def _fetch_data(self, query: DataQuery) -> list[DataPoint]:
        """从AlphaVantage获取数据."""
        data_points: list[DataPoint] = []

        if not query.symbols:
            return data_points

        for symbol in query.symbols:
            try:
                symbol_data = await self._fetch_symbol_data(symbol, query)
                data_points.extend(symbol_data)
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
                continue

        return data_points

    async def _fetch_symbol_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取单个符号的数据."""
        data_points = []

        # 根据资产类型选择不同的API函数
        if query.asset == AssetType.STOCK:
            data_points = await self._fetch_stock_data(symbol, query)
        elif query.asset == AssetType.FOREX:
            data_points = await self._fetch_forex_data(symbol, query)
        elif query.asset == AssetType.CRYPTO:
            data_points = await self._fetch_crypto_data(symbol, query)
        else:
            data_points = await self._fetch_stock_data(symbol, query)  # 默认为股票

        return data_points

    async def _fetch_stock_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取股票数据."""
        data_points = []

        # 根据时间框架选择不同的函数
        timeframe = query.timeframe or TimeFrame.DAY_1

        function_mapping = {
            TimeFrame.MINUTE_1: "TIME_SERIES_INTRADAY",
            TimeFrame.MINUTE_5: "TIME_SERIES_INTRADAY",
            TimeFrame.MINUTE_15: "TIME_SERIES_INTRADAY",
            TimeFrame.MINUTE_30: "TIME_SERIES_INTRADAY",
            TimeFrame.HOUR_1: "TIME_SERIES_INTRADAY",
            TimeFrame.DAY_1: "TIME_SERIES_DAILY",
            TimeFrame.WEEK_1: "TIME_SERIES_WEEKLY",
            TimeFrame.MONTH_1: "TIME_SERIES_MONTHLY",
        }

        function = function_mapping.get(timeframe, "TIME_SERIES_DAILY")
        interval = self._get_interval_param(timeframe)

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
            "outputsize": "full",
        }

        if interval and function == "TIME_SERIES_INTRADAY":
            params["interval"] = interval

        url = f"{self.BASE_URL}"

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, params=params) as response,
        ):
            data = await response.json()

            if "Error Message" in data:
                raise ProviderError(f"AlphaVantage API error: {data['Error Message']}", "AlphaVantage")

            if "Note" in data:
                raise ProviderError(f"AlphaVantage rate limit: {data['Note']}", "AlphaVantage")

            data_points = self._parse_alpha_vantage_response(data, symbol, function, query.market or "us")

        return data_points

    async def _fetch_forex_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取外汇数据."""
        data_points = []

        # 解析货币对
        from_currency, to_currency = symbol[:3], symbol[3:]

        timeframe = query.timeframe or TimeFrame.DAY_1

        function_mapping = {
            TimeFrame.MINUTE_1: "FX_INTRADAY",
            TimeFrame.MINUTE_5: "FX_INTRADAY",
            TimeFrame.MINUTE_15: "FX_INTRADAY",
            TimeFrame.MINUTE_30: "FX_INTRADAY",
            TimeFrame.HOUR_1: "FX_INTRADAY",
            TimeFrame.DAY_1: "FX_DAILY",
            TimeFrame.WEEK_1: "FX_WEEKLY",
            TimeFrame.MONTH_1: "FX_MONTHLY",
        }

        function = function_mapping.get(timeframe, "FX_DAILY")
        interval = self._get_interval_param(timeframe)

        params = {
            "function": function,
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "apikey": self.api_key,
        }

        if interval and function == "FX_INTRADAY":
            params["interval"] = interval

        url = f"{self.BASE_URL}"

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, params=params) as response,
        ):
            data = await response.json()

            if "Error Message" in data:
                raise ProviderError(f"AlphaVantage API error: {data['Error Message']}", "AlphaVantage")

            data_points = self._parse_alpha_vantage_response(data, symbol, function, query.market or "global")

        return data_points

    async def _fetch_crypto_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取加密货币数据."""
        data_points = []

        # 解析加密货币对
        market = "USD"  # 默认以USD计价

        timeframe = query.timeframe or TimeFrame.DAY_1

        function_mapping = {
            TimeFrame.MINUTE_1: "CRYPTO_INTRADAY",
            TimeFrame.MINUTE_5: "CRYPTO_INTRADAY",
            TimeFrame.MINUTE_15: "CRYPTO_INTRADAY",
            TimeFrame.MINUTE_30: "CRYPTO_INTRADAY",
            TimeFrame.HOUR_1: "CRYPTO_INTRADAY",
            TimeFrame.DAY_1: "DIGITAL_CURRENCY_DAILY",
            TimeFrame.WEEK_1: "DIGITAL_CURRENCY_WEEKLY",
            TimeFrame.MONTH_1: "DIGITAL_CURRENCY_MONTHLY",
        }

        function = function_mapping.get(timeframe, "DIGITAL_CURRENCY_DAILY")
        interval = self._get_interval_param(timeframe)

        params = {
            "function": function,
            "symbol": symbol,
            "market": market,
            "apikey": self.api_key,
        }

        if interval and function == "CRYPTO_INTRADAY":
            params["interval"] = interval

        url = f"{self.BASE_URL}"

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, params=params) as response,
        ):
            data = await response.json()

            if "Error Message" in data:
                raise ProviderError(f"AlphaVantage API error: {data['Error Message']}", "AlphaVantage")

            data_points = self._parse_alpha_vantage_response(data, symbol, function, market)

        return data_points

    def _get_interval_param(self, timeframe: TimeFrame) -> str | None:
        """将时间框架转换为AlphaVantage间隔参数."""
        mapping = {
            TimeFrame.MINUTE_1: "1min",
            TimeFrame.MINUTE_5: "5min",
            TimeFrame.MINUTE_15: "15min",
            TimeFrame.MINUTE_30: "30min",
            TimeFrame.HOUR_1: "60min",
        }
        return mapping.get(timeframe)

    def _parse_alpha_vantage_response(self, data: dict[str, Any], symbol: str, function: str, market: str) -> list[DataPoint]:
        """解析AlphaVantage响应."""
        data_points: list[DataPoint] = []

        # 根据函数类型选择正确的数据键
        data_key_mapping = {
            "TIME_SERIES_INTRADAY": "Time Series",
            "TIME_SERIES_DAILY": "Time Series (Daily)",
            "TIME_SERIES_WEEKLY": "Weekly Time Series",
            "TIME_SERIES_MONTHLY": "Monthly Time Series",
            "FX_INTRADAY": "Time Series FX",
            "FX_DAILY": "Time Series FX (Daily)",
            "FX_WEEKLY": "Weekly Time Series FX",
            "FX_MONTHLY": "Monthly Time Series FX",
            "CRYPTO_INTRADAY": "Time Series Crypto",
            "DIGITAL_CURRENCY_DAILY": "Time Series (Digital Currency Daily)",
            "DIGITAL_CURRENCY_WEEKLY": "Time Series (Digital Currency Weekly)",
            "DIGITAL_CURRENCY_MONTHLY": "Time Series (Digital Currency Monthly)",
        }

        data_key = None
        for key in data_key_mapping.values():
            if key in data:
                data_key = key
                break

        if not data_key or data_key not in data:
            return data_points

        time_series = data[data_key]

        for date_str, values in time_series.items():
            try:
                # 解析日期
                timestamp = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S") if " " in date_str else datetime.strptime(date_str, "%Y-%m-%d")

                # 解析数值
                # 解析数值
                open_price = Decimal(str(values.get("1. open", values.get("1. open", 0))))
                high_price = Decimal(str(values.get("2. high", values.get("2. high", 0))))
                low_price = Decimal(str(values.get("3. low", values.get("3. low", 0))))
                close_price = Decimal(str(values.get("4. close", values.get("4. close", 0))))
                volume = Decimal(str(values.get("5. volume", values.get("5. volume", 0))))

                data_point = DataPoint(
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
                data_points.append(data_point)
            except Exception as e:
                print(f"Error parsing AlphaVantage data: {e}")
                continue

        # 按时间排序
        data_points.sort(key=lambda x: x.timestamp)

        return data_points

    async def health_check(self) -> bool:
        """检查提供商健康状况."""
        return await self.authenticate()
