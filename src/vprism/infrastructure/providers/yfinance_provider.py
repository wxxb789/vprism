"""Yahoo Finance数据提供商实现."""

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import yfinance as yf

from vprism.core.exceptions import ProviderError
from vprism.core.models import (
    DataPoint,
    DataQuery,
    DataResponse,
    TimeFrame,
)

from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)


class YFinanceProvider(DataProvider):
    """Yahoo Finance数据提供商实现."""

    def __init__(self):
        """初始化YFinance提供商."""
        auth_config = AuthConfig(
            auth_type=AuthType.NONE, credentials={}, required_fields=[]
        )

        rate_limit = RateLimitConfig(
            requests_per_minute=2000,  # Yahoo Finance相对宽松
            requests_per_hour=10000,
            requests_per_day=100000,
            concurrent_requests=10,
            backoff_factor=1.0,
            max_retries=3,
            initial_delay=0.1,
        )

        super().__init__("yfinance", auth_config, rate_limit)

    def _discover_capability(self) -> ProviderCapability:
        """发现YFinance能力."""
        return ProviderCapability(
            supported_assets={
                "stock",
                "etf",
                "index",
                "crypto",
                "forex",
                "futures",
                "options",
            },
            supported_markets={"us", "global"},  # Yahoo Finance主要覆盖美股和全球市场
            supported_timeframes={
                "1m",
                "2m",
                "5m",
                "15m",
                "30m",
                "1h",
                "1d",
                "5d",
                "1wk",
                "1mo",
                "3mo",
            },
            max_symbols_per_request=100,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=15,  # 延迟约15秒
            rate_limits={
                "requests_per_minute": 2000,
                "requests_per_hour": 10000,
                "requests_per_day": 100000,
            },
        )

    async def authenticate(self) -> bool:
        """YFinance不需要认证."""
        self._is_authenticated = True
        return True

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据."""
        if not self.can_handle_query(query):
            raise ProviderError(f"YFinance cannot handle query: {query}", "yfinance")

        try:
            data_points = await self._fetch_data(query)

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "query_time_ms": 0,
                    "data_source": "yfinance",
                    "cache_hit": False,
                },
                source={
                    "name": "yfinance",
                    "version": "latest",
                    "endpoint": "https://finance.yahoo.com/",
                },
                cached=False,
            )

        except Exception as e:
            raise ProviderError(
                f"Failed to fetch data from yfinance: {e}", "yfinance"
            ) from e

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def _fetch_data(self, query: DataQuery) -> list[DataPoint]:
        """从yfinance获取数据."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_fetch_data, query
        )

    def _sync_fetch_data(self, query: DataQuery) -> list[DataPoint]:
        """同步获取数据."""
        data_points = []

        if not query.symbols:
            return data_points

        for symbol in query.symbols:
            try:
                ticker = yf.Ticker(symbol)

                # 根据时间框架获取历史数据
                period, interval = self._get_yfinance_params(query)

                # 获取历史数据
                hist = ticker.history(
                    period=period, interval=interval, start=query.start, end=query.end
                )

                if hist.empty:
                    continue

                # 转换为DataPoint
                for index, row in hist.iterrows():
                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=index.to_pydatetime(),
                        open=Decimal(str(row["Open"])),
                        high=Decimal(str(row["High"])),
                        low=Decimal(str(row["Low"])),
                        close=Decimal(str(row["Close"])),
                        volume=Decimal(str(row["Volume"])),
                        amount=Decimal(str(row["Close"])) * Decimal(str(row["Volume"])),
                    )
                    data_points.append(data_point)

            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
                continue

        return data_points

    def _get_yfinance_params(self, query: DataQuery) -> tuple:
        """将查询参数转换为yfinance参数."""
        # 时间段
        period = "1y"  # 默认1年
        if query.start and query.end:
            period = None  # 使用start/end
        elif query.timeframe:
            # 根据时间框架推断合适的period
            timeframe = query.timeframe
            if timeframe in [TimeFrame.TICK, TimeFrame.MINUTE_1, TimeFrame.MINUTE_5]:
                period = "1d"
            elif timeframe in [
                TimeFrame.MINUTE_15,
                TimeFrame.MINUTE_30,
                TimeFrame.HOUR_1,
            ]:
                period = "5d"
            elif timeframe == TimeFrame.DAY_1:
                period = "1mo"
            elif timeframe == TimeFrame.WEEK_1:
                period = "3mo"
            elif timeframe == TimeFrame.MONTH_1:
                period = "1y"

        # 时间间隔
        interval = "1d"  # 默认日线
        if query.timeframe:
            timeframe_mapping = {
                TimeFrame.MINUTE_1: "1m",
                TimeFrame.MINUTE_5: "5m",
                TimeFrame.MINUTE_15: "15m",
                TimeFrame.MINUTE_30: "30m",
                TimeFrame.HOUR_1: "1h",
                TimeFrame.DAY_1: "1d",
                TimeFrame.WEEK_1: "1wk",
                TimeFrame.MONTH_1: "1mo",
            }
            interval = timeframe_mapping.get(query.timeframe, "1d")

        return period, interval
