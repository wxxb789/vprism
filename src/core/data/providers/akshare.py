"""akshare数据提供商实现."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

from core.exceptions.base import ProviderError
from core.monitoring import StructuredLogger
from core.models.market import AssetType, MarketType, TimeFrame
from core.models.base import DataPoint
from core.models.query import DataQuery
from core.models.response import DataResponse

from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)

logger = StructuredLogger().logger


class AkShare(DataProvider):
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
        self._initialized = False

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
                "forex",
                "crypto",
            },
            supported_markets={"cn", "us", "hk", "global"},
            supported_timeframes={
                "1min",
                "5min",
                "15min",
                "30min",
                "60min",
                "1d",
                "1w",
                "1m",
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
        """与AkShare进行身份验证.

        AkShare不需要身份验证，只需要检查依赖是否可用。
        """
        try:
            import akshare as ak

            # 测试连接
            test_data = ak.stock_zh_a_spot()
            if test_data is not None and not test_data.empty:
                self._is_authenticated = True
                self._initialized = True
                logger.info("Successfully connected to AkShare")
                return True
            else:
                logger.error("Failed to connect to AkShare")
                return False

        except ImportError:
            logger.error("akshare package is not available")
            return False
        except Exception as e:
            logger.error(f"AkShare connection failed: {e}")
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据."""
        if not self._initialized:
            await self.authenticate()

        if not self._is_authenticated:
            raise RuntimeError("AkShare provider not initialized")

        if not self.can_handle_query(query):
            raise ProviderError(f"AkShare cannot handle query: {query}", "akshare")

        try:
            return await self._fetch_data(query)

        except Exception as e:
            logger.error(f"Error getting data from AkShare: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def _fetch_data(self, query: DataQuery) -> DataResponse:
        """获取数据的核心方法."""
        if not query.symbols:
            return DataResponse(data=[], metadata={"error": "No symbols provided"})

        symbol = query.symbols[0]
        market = query.market.value if query.market else "cn"

        try:
            if market == "cn":
                return await self._get_cn_data(symbol, query)
            elif market == "us":
                return await self._get_us_data(symbol, query)
            elif market == "hk":
                return await self._get_hk_data(symbol, query)
            else:
                return DataResponse(
                    data=[], metadata={"error": f"Unsupported market: {market}"}
                )

        except Exception as e:
            logger.error(f"Error fetching data from AkShare: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def _get_cn_data(self, symbol: str, query: DataQuery) -> DataResponse:
        """获取中国市场数据."""
        try:
            import akshare as ak
            import pandas as pd
        except ImportError as e:
            raise RuntimeError(f"Required dependencies not available: {e}")

        # 转换时间框架
        timeframe_map = {
            "1min": "1",
            "5min": "5",
            "15min": "15",
            "30min": "30",
            "60min": "60",
            "1d": "daily",
            "1w": "weekly",
            "1m": "monthly",
        }

        ak_timeframe = timeframe_map.get(
            query.timeframe.value if query.timeframe else "1d", "daily"
        )

        try:
            # 根据资产类型选择不同的接口
            if query.asset == AssetType.STOCK:
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=ak_timeframe,
                    start_date=query.start.strftime("%Y%m%d") if query.start else None,
                    end_date=query.end.strftime("%Y%m%d") if query.end else None,
                    adjust="",
                )
            elif query.asset == AssetType.INDEX:
                df = ak.index_zh_a_hist(symbol=symbol)
            elif query.asset == AssetType.ETF:
                df = ak.fund_etf_fund_info_em(symbol=symbol)
            else:
                return DataResponse(
                    data=[],
                    metadata={"error": f"Unsupported asset type: {query.asset}"},
                )

            if df is None or df.empty:
                return DataResponse(data=[], metadata={"message": "No data found"})

            data_points = []
            for _, row in df.iterrows():
                try:
                    # 处理列名映射
                    if query.asset == AssetType.STOCK:
                        date_col = "日期" if "日期" in df.columns else "date"
                        open_col = "开盘" if "开盘" in df.columns else "open"
                        high_col = "最高" if "最高" in df.columns else "high"
                        low_col = "最低" if "最低" in df.columns else "low"
                        close_col = "收盘" if "收盘" in df.columns else "close"
                        vol_col = "成交量" if "成交量" in df.columns else "volume"

                        timestamp = pd.to_datetime(str(row[date_col]))
                        data_point = DataPoint(
                            symbol=symbol,
                            market=MarketType.CN,
                            timestamp=timestamp,
                            open_price=Decimal(str(row[open_col])),
                            high_price=Decimal(str(row[high_col])),
                            low_price=Decimal(str(row[low_col])),
                            close_price=Decimal(str(row[close_col])),
                            volume=Decimal(str(row[vol_col])),
                            provider="akshare",
                        )
                    elif query.asset == AssetType.INDEX:
                        date_col = "日期" if "日期" in df.columns else "date"
                        open_col = "开盘" if "开盘" in df.columns else "open"
                        high_col = "最高" if "最高" in df.columns else "high"
                        low_col = "最低" if "最低" in df.columns else "low"
                        close_col = "收盘" if "收盘" in df.columns else "close"
                        vol_col = "成交量" if "成交量" in df.columns else "volume"

                        timestamp = pd.to_datetime(str(row[date_col]))
                        data_point = DataPoint(
                            symbol=symbol,
                            market=MarketType.CN,
                            timestamp=timestamp,
                            open_price=Decimal(str(row[open_col])),
                            high_price=Decimal(str(row[high_col])),
                            low_price=Decimal(str(row[low_col])),
                            close_price=Decimal(str(row[close_col])),
                            volume=Decimal(str(row[vol_col])),
                            provider="akshare",
                        )
                    elif query.asset == AssetType.ETF:
                        date_col = "净值日期" if "净值日期" in df.columns else "date"
                        close_col = "单位净值" if "单位净值" in df.columns else "close"

                        timestamp = pd.to_datetime(str(row[date_col]))
                        data_point = DataPoint(
                            symbol=symbol,
                            market=MarketType.CN,
                            timestamp=timestamp,
                            close_price=Decimal(str(row[close_col])),
                            provider="akshare",
                        )

                    data_points.append(data_point)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping row due to error: {e}")
                    continue

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "source": "akshare",
                    "symbol": symbol,
                    "market": "cn",
                },
            )

        except Exception as e:
            logger.error(f"Error getting Chinese data: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def _get_us_data(self, symbol: str, query: DataQuery) -> DataResponse:
        """获取美国市场数据."""
        try:
            import akshare as ak
            import pandas as pd
        except ImportError as e:
            raise RuntimeError(f"Required dependencies not available: {e}")

        try:
            if query.asset == AssetType.STOCK:
                df = ak.stock_us_daily(symbol=symbol, adjust="")
            elif query.asset == AssetType.INDEX:
                df = ak.index_us_stock_sina(symbol=symbol)
            else:
                return DataResponse(
                    data=[],
                    metadata={"error": f"Unsupported asset type: {query.asset}"},
                )

            if df is None or df.empty:
                return DataResponse(data=[], metadata={"message": "No data found"})

            # 过滤日期范围
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                if query.start:
                    df = df[df["date"] >= pd.to_datetime(query.start)]
                if query.end:
                    df = df[df["date"] <= pd.to_datetime(query.end)]

            if df.empty:
                return DataResponse(
                    data=[], metadata={"message": "No data in date range"}
                )

            data_points = []
            for _, row in df.iterrows():
                try:
                    timestamp = row["date"] if "date" in row else datetime.now()
                    data_point = DataPoint(
                        symbol=symbol,
                        market=MarketType.US,
                        timestamp=timestamp,
                        open_price=Decimal(str(row.get("open", 0))),
                        high_price=Decimal(str(row.get("high", 0))),
                        low_price=Decimal(str(row.get("low", 0))),
                        close_price=Decimal(str(row.get("close", 0))),
                        volume=Decimal(str(row.get("volume", 0))),
                        provider="akshare",
                    )
                    data_points.append(data_point)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping row due to error: {e}")
                    continue

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "source": "akshare",
                    "symbol": symbol,
                    "market": "us",
                },
            )

        except Exception as e:
            logger.error(f"Error getting US data: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def _get_hk_data(self, symbol: str, query: DataQuery) -> DataResponse:
        """获取香港市场数据."""
        try:
            import akshare as ak
            import pandas as pd
        except ImportError as e:
            raise RuntimeError(f"Required dependencies not available: {e}")

        try:
            if query.asset == AssetType.STOCK:
                df = ak.stock_hk_daily(symbol=symbol, adjust="")
            else:
                return DataResponse(
                    data=[],
                    metadata={"error": f"Unsupported asset type: {query.asset}"},
                )

            if df is None or df.empty:
                return DataResponse(data=[], metadata={"message": "No data found"})

            # 过滤日期范围
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                if query.start:
                    df = df[df["date"] >= pd.to_datetime(query.start)]
                if query.end:
                    df = df[df["date"] <= pd.to_datetime(query.end)]

            if df.empty:
                return DataResponse(
                    data=[], metadata={"message": "No data in date range"}
                )

            data_points = []
            for _, row in df.iterrows():
                try:
                    timestamp = row["date"] if "date" in row else datetime.now()
                    data_point = DataPoint(
                        symbol=symbol,
                        market=MarketType.HK,
                        timestamp=timestamp,
                        open_price=Decimal(str(row.get("open", 0))),
                        high_price=Decimal(str(row.get("high", 0))),
                        low_price=Decimal(str(row.get("low", 0))),
                        close_price=Decimal(str(row.get("close", 0))),
                        volume=Decimal(str(row.get("volume", 0))),
                        provider="akshare",
                    )
                    data_points.append(data_point)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping row due to error: {e}")
                    continue

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "source": "akshare",
                    "symbol": symbol,
                    "market": "hk",
                },
            )

        except Exception as e:
            logger.error(f"Error getting Hong Kong data: {e}")
            return DataResponse(data=[], metadata={"error": str(e)})

    async def get_real_time_quote(self, symbol: str, market: str = "cn") -> dict | None:
        """获取实时报价."""
        if not self._initialized:
            await self.authenticate()

        if not self._is_authenticated:
            logger.error("AkShare provider not initialized")
            return None

        try:
            import akshare as ak

            if market == "cn":
                # 获取中国实时行情
                df = ak.stock_zh_a_spot()
                if df is not None and not df.empty:
                    row = (
                        df[df["代码"] == symbol].iloc[0]
                        if symbol in df["代码"].values
                        else None
                    )
                    if row is not None:
                        return {
                            "symbol": symbol,
                            "price": Decimal(str(row["最新价"])),
                            "change": Decimal(str(row["涨跌额"])),
                            "change_percent": Decimal(str(row["涨跌幅"])),
                            "volume": Decimal(str(row["成交量"])),
                            "timestamp": datetime.now(),
                        }
            elif market == "us":
                # 获取美国实时行情
                df = ak.stock_us_spot()
                if df is not None and not df.empty:
                    row = (
                        df[df["symbol"] == symbol].iloc[0]
                        if symbol in df["symbol"].values
                        else None
                    )
                    if row is not None:
                        return {
                            "symbol": symbol,
                            "price": Decimal(str(row["price"])),
                            "change": Decimal(str(row["change"])),
                            "change_percent": Decimal(str(row["change_percent"])),
                            "volume": Decimal(str(row["volume"])),
                            "timestamp": datetime.now(),
                        }

        except Exception as e:
            logger.error(f"Error getting real-time quote from AkShare: {e}")

        return None
