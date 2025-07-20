"""Yahoo Finance数据提供商实现."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from vprism.core.models import DataPoint, DataQuery, DataResponse, MarketType, TimeFrame
from vprism.infrastructure.providers.base import (
    AuthConfig,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)

logger = logging.getLogger(__name__)


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance数据提供商实现."""

    def __init__(self, auth_config: AuthConfig, rate_limit: RateLimitConfig):
        """初始化Yahoo Finance提供商.

        Args:
            auth_config: 认证配置
            rate_limit: 速率限制配置
        """
        super().__init__("yahoo", auth_config, rate_limit)

    def _discover_capability(self) -> ProviderCapability:
        """发现Yahoo Finance能力."""
        return ProviderCapability(
            supported_assets={"stock", "index", "etf", "crypto", "forex"},
            supported_markets={"us", "global"},
            supported_timeframes={"1min", "2min", "5min", "15min", "30min", "60min", "90min", "1h", "1d", "5d", "1wk", "1mo", "3mo"},
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
        if not YFINANCE_AVAILABLE:
            logger.error("yfinance package is not available")
            return False

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

        try:
            # 根据查询类型获取数据
            return await self._get_historical_data(query)

        except Exception as e:
            logger.error(f"Error getting data from Yahoo Finance: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        response = await self.get_data(query)
        for data_point in response.data:
            yield data_point

    async def _get_historical_data(self, query: DataQuery) -> DataResponse:
        """获取历史数据."""
        if not query.symbols:
            return DataResponse(data=[], metadata={"error": "No symbols provided"})

        symbol = query.symbols[0]
        
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
            "3mo": "3mo"
        }
        
        yf_timeframe = timeframe_map.get(query.timeframe.value, "1d")
        
        try:
            ticker = yf.Ticker(symbol)
            
            if yf_timeframe == "1d":
                # 日线数据
                data = ticker.history(
                    start=query.start_date,
                    end=query.end_date,
                    interval=yf_timeframe
                )
            else:
                # 分钟级数据
                data = ticker.history(
                    start=query.start_date,
                    end=query.end_date,
                    interval=yf_timeframe
                )

            if data is None or data.empty:
                return DataResponse(data=[], metadata={"message": "No data found"})

            data_points = []
            for date, row in data.iterrows():
                # 确定市场类型
                market = MarketType.US
                if symbol.endswith(".HK"):
                    market = MarketType.HK
                elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
                    market = MarketType.CN
                elif symbol.endswith(".T") or symbol.endswith(".TO"):
                    market = MarketType.JP
                elif symbol.endswith(".L"):
                    market = MarketType.UK
                elif symbol.endswith(".AX"):
                    market = MarketType.AU

                data_point = DataPoint(
                    symbol=symbol,
                    market=market,
                    timestamp=date,
                    open_price=Decimal(str(row["Open"])),
                    high_price=Decimal(str(row["High"])),
                    low_price=Decimal(str(row["Low"])),
                    close_price=Decimal(str(row["Close"])),
                    volume=Decimal(str(int(row["Volume"]))),
                    provider="yahoo"
                )
                data_points.append(data_point)

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "source": "yahoo",
                    "symbol": symbol,
                    "timeframe": yf_timeframe
                }
            )

        except Exception as e:
            logger.error(f"Error getting historical data from Yahoo Finance: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def get_real_time_quote(self, symbol: str) -> Optional[dict]:
        """获取实时报价."""
        if not self._is_authenticated:
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if info:
                # 确定市场类型
                market = MarketType.US
                if symbol.endswith(".HK"):
                    market = MarketType.HK
                elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
                    market = MarketType.CN
                elif symbol.endswith(".T") or symbol.endswith(".TO"):
                    market = MarketType.JP
                elif symbol.endswith(".L"):
                    market = MarketType.UK
                elif symbol.endswith(".AX"):
                    market = MarketType.AU

                return {
                    "symbol": symbol,
                    "price": Decimal(str(info.get("currentPrice", info.get("regularMarketPrice", 0)))),
                    "change": Decimal(str(info.get("regularMarketChange", 0))),
                    "change_percent": Decimal(str(info.get("regularMarketChangePercent", 0))),
                    "volume": Decimal(str(info.get("regularMarketVolume", 0))),
                    "previous_close": Decimal(str(info.get("regularMarketPreviousClose", 0))),
                    "timestamp": datetime.now(),
                    "market": market
                }

        except Exception as e:
            logger.error(f"Error getting real-time quote from Yahoo Finance: {e}")

        return None

    async def get_company_info(self, symbol: str) -> Optional[dict]:
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
                    "description": info.get("longBusinessSummary", "")
                }

        except Exception as e:
            logger.error(f"Error getting company info from Yahoo Finance: {e}")

        return None