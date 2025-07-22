"""akshare数据提供商实现."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

import akshare as ak

from vprism.core.exceptions import ProviderError
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    TimeFrame,
)

from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)


class AkShareProvider(DataProvider):
    """akshare数据提供商实现."""

    def __init__(
        self, auth_config: AuthConfig = None, rate_limit: RateLimitConfig = None
    ):
        """初始化akshare提供商."""
        if auth_config is None:
            auth_config = AuthConfig(
                auth_type=AuthType.NONE, credentials={}, required_fields=[]
            )

        if rate_limit is None:
            rate_limit = RateLimitConfig(
                requests_per_minute=1000,
                requests_per_hour=5000,
                requests_per_day=20000,
                concurrent_requests=8,
                backoff_factor=2.0,
                max_retries=3,
                initial_delay=1.0,
            )

        super().__init__("akshare", auth_config, rate_limit)

    def _discover_capability(self) -> ProviderCapability:
        """发现akshare能力."""
        return ProviderCapability(
            supported_assets={
                "stock",
                "bond",
                "etf",
                "fund",
                "futures",
                "options",
                "index",
            },
            supported_markets={"cn", "us", "hk", "global"},
            supported_timeframes={
                "tick",
                "1m",
                "5m",
                "15m",
                "30m",
                "1h",
                "4h",
                "1d",
                "1w",
                "1M",
            },
            max_symbols_per_request=100,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
            rate_limits={
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_day": 10000,
            },
        )

    async def authenticate(self) -> bool:
        """akshare不需要认证."""
        self._is_authenticated = True
        return True

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据."""
        if not self.can_handle_query(query):
            raise ProviderError(f"AkShare cannot handle query: {query}", "akshare")

        try:
            data_points = await self._fetch_data(query)

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "query_time_ms": 0,  # 实际实现应计算查询时间
                    "data_source": "akshare",
                    "cache_hit": False,
                },
                source={
                    "name": "akshare",
                    "version": ak.__version__,
                    "endpoint": "https://www.akshare.xyz/",
                },
                cached=False,
            )

        except Exception as e:
            raise ProviderError(
                f"Failed to fetch data from akshare: {e}", "akshare"
            ) from e

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def _fetch_data(self, query: DataQuery) -> list[DataPoint]:
        """从akshare获取数据."""
        # 在事件循环中运行同步的akshare调用
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_fetch_data, query
        )

    def _sync_fetch_data(self, query: DataQuery) -> list[DataPoint]:
        """同步获取数据."""
        data_points = []

        if query.asset == AssetType.STOCK:
            data_points = self._fetch_stock_data(query)
        elif query.asset == AssetType.INDEX:
            data_points = self._fetch_index_data(query)
        elif query.asset == AssetType.ETF:
            data_points = self._fetch_etf_data(query)
        else:
            raise ProviderError(f"Unsupported asset type: {query.asset}", "akshare")

        return data_points

    def _fetch_stock_data(self, query: DataQuery) -> list[DataPoint]:
        """获取股票数据."""
        data_points = []

        for symbol in query.symbols or []:
            try:
                # 根据市场选择不同的akshare接口
                if query.market == MarketType.CN:
                    data = self._fetch_cn_stock_data(symbol, query)
                elif query.market == MarketType.US:
                    data = self._fetch_us_stock_data(symbol, query)
                elif query.market == MarketType.HK:
                    data = self._fetch_hk_stock_data(symbol, query)
                else:
                    continue

                data_points.extend(data)

            except Exception as e:
                # 记录错误但继续处理其他符号
                print(f"Error fetching data for {symbol}: {e}")
                continue

        return data_points

    def _fetch_cn_stock_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取中国股票数据."""
        data_points = []

        # 根据时间框架选择不同的接口
        timeframe = query.timeframe or TimeFrame.DAY_1

        if timeframe == TimeFrame.DAY_1:
            # 获取日线数据
            try:
                # 使用akshare的历史行情接口
                kwargs = {
                    "symbol": symbol,
                    "period": "daily",
                    "adjust": ""
                }
                
                # 只在有具体日期时添加日期参数，避免空字符串导致无数据
                if query.start:
                    kwargs["start_date"] = query.start.strftime("%Y%m%d")
                if query.end:
                    kwargs["end_date"] = query.end.strftime("%Y%m%d")
                
                stock_zh_a_hist_df = ak.stock_zh_a_hist(**kwargs)

                for _, row in stock_zh_a_hist_df.iterrows():
                    # 解析日期，处理可能的多种格式
                    date_str = str(row["日期"])
                    try:
                        # 处理YYYY-MM-DD格式
                        if len(date_str) >= 10:
                            date_part = date_str[:10]  # 只取日期部分
                            timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                        else:
                            timestamp = datetime.fromisoformat(date_str)
                    except (ValueError, TypeError):
                        # 回退方案：使用当前日期
                        timestamp = datetime.now()
                    
                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=Decimal(str(row["开盘"])),
                        high=Decimal(str(row["最高"])),
                        low=Decimal(str(row["最低"])),
                        close=Decimal(str(row["收盘"])),
                        volume=Decimal(str(row["成交量"])),
                        amount=Decimal(str(row["成交额"])) if "成交额" in row else None,
                    )
                    data_points.append(data_point)

            except Exception as e:
                print(f"Error fetching CN stock data for {symbol}: {e}")

        return data_points

    def _fetch_us_stock_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取美股数据."""
        data_points = []

        try:
            # 使用akshare的美股接口
            stock_us_hist_df = ak.stock_us_daily(symbol=symbol)

            # 过滤日期范围
            if query.start:
                stock_us_hist_df = stock_us_hist_df[
                    stock_us_hist_df["date"] >= query.start
                ]
            if query.end:
                stock_us_hist_df = stock_us_hist_df[
                    stock_us_hist_df["date"] <= query.end
                ]

            for _, row in stock_us_hist_df.iterrows():
                # 解析日期，处理可能的多种格式
                date_str = str(row["date"])
                try:
                    # 处理YYYY-MM-DD格式
                    if len(date_str) >= 10:
                        date_part = date_str[:10]  # 只取日期部分
                        timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                    else:
                        timestamp = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    # 回退方案：使用当前日期
                    timestamp = datetime.now()
                
                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                    amount=Decimal(str(row["close"])) * Decimal(str(row["volume"])),
                )
                data_points.append(data_point)

        except Exception as e:
            print(f"Error fetching US stock data for {symbol}: {e}")

        return data_points

    def _fetch_hk_stock_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取港股数据."""
        data_points = []

        try:
            # 使用akshare的港股接口
            stock_hk_hist_df = ak.stock_hk_daily(symbol=symbol)

            # 过滤日期范围
            if query.start:
                stock_hk_hist_df = stock_hk_hist_df[
                    stock_hk_hist_df["date"] >= query.start
                ]
            if query.end:
                stock_hk_hist_df = stock_hk_hist_df[
                    stock_hk_hist_df["date"] <= query.end
                ]

            for _, row in stock_hk_hist_df.iterrows():
                # 解析日期，处理可能的多种格式
                date_str = str(row["date"])
                try:
                    # 处理YYYY-MM-DD格式
                    if len(date_str) >= 10:
                        date_part = date_str[:10]  # 只取日期部分
                        timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                    else:
                        timestamp = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    # 回退方案：使用当前日期
                    timestamp = datetime.now()
                
                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                    amount=Decimal(str(row["close"])) * Decimal(str(row["volume"])),
                )
                data_points.append(data_point)

        except Exception as e:
            print(f"Error fetching HK stock data for {symbol}: {e}")

        return data_points

    def _fetch_index_data(self, query: DataQuery) -> list[DataPoint]:
        """获取指数数据."""
        data_points = []

        for symbol in query.symbols or []:
            try:
                # 根据市场选择不同的指数接口
                if query.market == MarketType.CN:
                    # 获取中国指数数据
                    index_zh_a_hist_df = ak.index_zh_a_hist(symbol=symbol)

                    for _, row in index_zh_a_hist_df.iterrows():
                        # 解析日期，处理可能的多种格式
                        date_str = str(row["日期"])
                        try:
                            # 处理YYYY-MM-DD格式
                            if len(date_str) >= 10:
                                date_part = date_str[:10]  # 只取日期部分
                                timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                            else:
                                timestamp = datetime.fromisoformat(date_str)
                        except (ValueError, TypeError):
                            # 回退方案：使用当前日期
                            timestamp = datetime.now()
                        
                        data_point = DataPoint(
                            symbol=symbol,
                            timestamp=timestamp,
                            open=Decimal(str(row["开盘"])),
                            high=Decimal(str(row["最高"])),
                            low=Decimal(str(row["最低"])),
                            close=Decimal(str(row["收盘"])),
                            volume=Decimal(str(row["成交量"])),
                        )
                        data_points.append(data_point)

                elif query.market == MarketType.US:
                    # 获取美股指数数据
                    index_us_stock_df = ak.index_us_stock_sina(symbol=symbol)

                    for _, row in index_us_stock_df.iterrows():
                        # 解析日期，处理可能的多种格式
                        date_str = str(row["date"])
                        try:
                            # 处理YYYY-MM-DD格式
                            if len(date_str) >= 10:
                                date_part = date_str[:10]  # 只取日期部分
                                timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                            else:
                                timestamp = datetime.fromisoformat(date_str)
                        except (ValueError, TypeError):
                            # 回退方案：使用当前日期
                            timestamp = datetime.now()
                        
                        data_point = DataPoint(
                            symbol=symbol,
                            timestamp=timestamp,
                            open=Decimal(str(row["open"])),
                            high=Decimal(str(row["high"])),
                            low=Decimal(str(row["low"])),
                            close=Decimal(str(row["close"])),
                            volume=Decimal(str(row["volume"])),
                        )
                        data_points.append(data_point)

            except Exception as e:
                print(f"Error fetching index data for {symbol}: {e}")
                continue

        return data_points

    def _fetch_etf_data(self, query: DataQuery) -> list[DataPoint]:
        """获取ETF数据."""
        data_points = []

        for symbol in query.symbols or []:
            try:
                # 获取ETF数据
                etf_df = ak.fund_etf_fund_info_em(symbol=symbol)

                # 过滤日期范围
                if query.start:
                    etf_df = etf_df[etf_df["净值日期"] >= query.start]
                if query.end:
                    etf_df = etf_df[etf_df["净值日期"] <= query.end]

                for _, row in etf_df.iterrows():
                    # 解析日期，处理可能的多种格式
                    date_str = str(row["净值日期"])
                    try:
                        # 处理YYYY-MM-DD格式
                        if len(date_str) >= 10:
                            date_part = date_str[:10]  # 只取日期部分
                            timestamp = datetime.strptime(date_part, "%Y-%m-%d")
                        else:
                            timestamp = datetime.fromisoformat(date_str)
                    except (ValueError, TypeError):
                        # 回退方案：使用当前日期
                        timestamp = datetime.now()
                    
                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=timestamp,
                        close=Decimal(str(row["单位净值"])),
                        # ETF数据可能没有开高低价格，只使用收盘价
                        open=None,
                        high=None,
                        low=None,
                        volume=None,
                        amount=None,
                    )
                    data_points.append(data_point)

            except Exception as e:
                print(f"Error fetching ETF data for {symbol}: {e}")
                continue

        return data_points
