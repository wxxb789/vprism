"""Yahoo Finance数据提供商实现."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

import yfinance as yf

from core.exceptions.base import ProviderError
from core.monitoring import StructuredLogger
from core.models.base import DataPoint
from core.models.query import DataQuery
from core.models.response import DataResponse
from core.models.market import MarketType
from core.models.response import ResponseMetadata
from core.models.market import TimeFrame

from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)


logger = StructuredLogger().logger


class YFinance(DataProvider):
    """Yahoo Finance数据提供商实现."""

    def __init__(self, auth_config=None, rate_limit=None):
        """初始化YFinance提供商.

        Args:
            auth_config: 认证配置
            rate_limit: 速率限制配置
        """
        auth_config = auth_config or AuthConfig(auth_type=AuthType.NONE, credentials={}, required_fields=[])
        rate_limit = rate_limit or RateLimitConfig(
            requests_per_minute=1000,
            requests_per_hour=5000,
            requests_per_day=20000,
            concurrent_requests=5,
        )

        super().__init__("yfinance", auth_config, rate_limit)

    def _discover_capability(self) -> ProviderCapability:
        """发现YFinance能力."""
        return ProviderCapability(
            supported_assets={
                "stock",
                "index",
                "etf",
                "crypto",
                "forex",
                "futures",
                "options",
            },
            supported_markets={"us", "global"},
            supported_timeframes={
                "1min",
                "2min",
                "5min",
                "15min",
                "30min",
                "60min",
                "90min",
                "1h",
                "1d",
                "5d",
                "1wk",
                "1mo",
                "3mo",
            },
            max_symbols_per_request=50,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
            rate_limits={
                "requests_per_minute": self.rate_limit.requests_per_minute,
                "requests_per_hour": self.rate_limit.requests_per_hour,
                "requests_per_day": self.rate_limit.requests_per_day,
            },
        )

    async def authenticate(self) -> bool:
        """与Yahoo Finance进行身份验证.

        Yahoo Finance不需要身份验证，只需要检查依赖是否可用。
        """
        try:
            # 测试连接
            ticker = yf.Ticker("AAPL")
            hist = ticker.history(period="1d")
            if hist is not None and not hist.empty:
                self._is_authenticated = True
                logger.info("Successfully connected to Yahoo Finance")
                return True
            else:
                logger.error("Failed to connect to Yahoo Finance")
                return False

        except Exception as e:
            logger.error(f"Yahoo Finance connection failed: {e}")
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据."""
        if not self._is_authenticated:
            await self.authenticate()

        if not self._is_authenticated:
            raise RuntimeError("Yahoo Finance provider not initialized")

        if not self.can_handle_query(query):
            raise ProviderError(f"YFinance cannot handle query: {query}", "yfinance")

        try:
            # 根据查询类型获取数据
            return await self._get_historical_data(query)

        except Exception as e:
            logger.error(f"Error getting data from Yahoo Finance: {e}")
            return DataResponse(
                data=[],
                metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="error"),
                source={"name": "yfinance", "endpoint": "error"},
            )

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    def _get_market_type(self, symbol: str) -> MarketType:
        """根据股票代码确定市场类型."""
        if symbol.endswith(".HK"):
            return MarketType.HK
        elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
            return MarketType.CN
        elif symbol.endswith(".T") or symbol.endswith(".TO"):
            return MarketType.JP
        elif symbol.endswith(".L"):
            return MarketType.UK
        elif symbol.endswith(".AX"):
            return MarketType.AU
        else:
            return MarketType.US

    async def _get_historical_data(self, query: DataQuery) -> DataResponse:
        """获取历史数据."""
        if not query.symbols:
            return DataResponse(
                data=[],
                metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="error"),
                source={"name": "yfinance", "endpoint": "error"},
            )

        symbol = query.symbols[0]  # 暂时只处理第一个符号

        # 转换时间框架
        timeframe_map = {
            "1min": "1m",
            "2min": "2m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "60min": "60m",
            "90min": "90m",
            "1h": "1h",
            "1d": "1d",
            "5d": "5d",
            "1wk": "1wk",
            "1mo": "1mo",
            "3mo": "3mo",
        }

        yf_timeframe = timeframe_map.get(query.timeframe.value, "1d")

        try:
            ticker = yf.Ticker(symbol)

            data = ticker.history(start=query.start_date, end=query.end_date, interval=yf_timeframe)

            if data is None or data.empty:
                return DataResponse(
                    data=[],
                    metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="yfinance"),
                    source={
                        "name": "yfinance",
                        "endpoint": "https://finance.yahoo.com/",
                    },
                )

            data_points = []
            for date, row in data.iterrows():
                market = self._get_market_type(symbol)

                data_point = DataPoint(
                    symbol=symbol,
                    market=market,
                    timestamp=date,
                    open_price=Decimal(str(row["Open"])),
                    high_price=Decimal(str(row["High"])),
                    low_price=Decimal(str(row["Low"])),
                    close_price=Decimal(str(row["Close"])),
                    volume=Decimal(str(int(row["Volume"]))),
                    provider="yfinance",
                )
                data_points.append(data_point)

            return DataResponse(
                data=data_points,
                metadata=ResponseMetadata(
                    total_records=len(data_points),
                    query_time_ms=0.0,
                    data_source="yfinance",
                ),
                source={"name": "yfinance", "endpoint": "https://finance.yahoo.com/"},
            )

        except Exception as e:
            logger.error(f"Error getting historical data from Yahoo Finance: {e}")
            return DataResponse(
                data=[],
                metadata=ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="error"),
                source={"name": "yfinance", "endpoint": "error"},
            )

    async def get_real_time_quote(self, symbol: str) -> dict | None:
        """获取实时报价."""
        if not self._is_authenticated:
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if info:
                market = self._get_market_type(symbol)

                return {
                    "symbol": symbol,
                    "price": Decimal(str(info.get("currentPrice", info.get("regularMarketPrice", 0)))),
                    "change": Decimal(str(info.get("regularMarketChange", 0))),
                    "change_percent": Decimal(str(info.get("regularMarketChangePercent", 0))),
                    "volume": Decimal(str(info.get("regularMarketVolume", 0))),
                    "previous_close": Decimal(str(info.get("regularMarketPreviousClose", 0))),
                    "timestamp": datetime.now(),
                    "market": market,
                }

        except Exception as e:
            logger.error(f"Error getting real-time quote from Yahoo Finance: {e}")

        return None

    async def get_company_info(self, symbol: str) -> dict | None:
        """获取公司信息."""
        if not self._is_authenticated:
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if info:
                return {
                    "symbol": symbol,
                    "name": info.get("longName", ""),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                    "market_cap": info.get("marketCap", 0),
                    "currency": info.get("currency", "USD"),
                    "exchange": info.get("exchange", ""),
                    "country": info.get("country", ""),
                    "description": info.get("longBusinessSummary", ""),
                }

        except Exception as e:
            logger.error(f"Error getting company info from Yahoo Finance: {e}")

        return None
