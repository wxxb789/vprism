"""akshare数据提供商实现."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from pydantic import ValidationError

from vprism.core.data.providers.base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)
from vprism.core.exceptions.base import ProviderError
from vprism.core.models.base import DataPoint
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from vprism.core.monitoring import StructuredLogger

logger = StructuredLogger().logger


class AkShare(DataProvider):
    """akshare数据提供商实现."""

    def __init__(self, auth_config: AuthConfig | None = None, rate_limit: RateLimitConfig | None = None) -> None:
        """初始化akshare提供商."""
        if auth_config is None:
            auth_config = AuthConfig(auth_type=AuthType.NONE, credentials={})

        if rate_limit is None:
            rate_limit = RateLimitConfig(requests_per_minute=60, requests_per_hour=1000, requests_per_day=5000, concurrent_requests=5)

        super().__init__(
            "akshare",
            auth_config,
            rate_limit,
        )
        self._initialized = False
        self._ak = None
        self._handler_map: dict[AssetType, Callable[[DataQuery], Any]] = {
            AssetType.STOCK: self._get_stock_data,
            AssetType.ETF: self._get_etf_data,
            AssetType.FUND: self._get_fund_data,
        }

    def _discover_capability(self) -> ProviderCapability:
        """发现akshare能力."""
        return ProviderCapability(
            supported_assets=set(self._handler_map.keys()),
            supported_markets={MarketType.CN, MarketType.US, MarketType.HK},
            supported_timeframes={"1d"},
            max_symbols_per_request=1,
            supports_real_time=True,
            supports_historical=True,
            data_delay_seconds=0,
        )

    async def _initialize_akshare(self):
        """Dynamically import and initialize akshare."""
        if self._ak:
            return
        try:
            import akshare as ak

            self._ak = ak
            logger.info("AkShare package is available.")
        except ImportError as e:
            logger.error("AkShare package not found. Please install it using 'pip install akshare'.")
            raise ProviderError(
                "AkShare package not installed",
                provider_name=self.name,
                code="DEPENDENCY_MISSING",
            ) from e

    async def authenticate(self) -> bool:
        """与AkShare进行身份验证."""
        try:
            await self._initialize_akshare()
            test_data = self._ak.stock_zh_a_spot_em()
            if test_data is not None and not test_data.empty:
                self._is_authenticated = True
                self._initialized = True
                logger.info("Successfully connected to AkShare.")
                return True
            logger.error("Failed to connect to AkShare: Test data fetch failed.")
            return False
        except Exception as e:
            logger.error(f"AkShare connection failed: {e}")
            return False

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取数据."""
        start_time = asyncio.get_event_loop().time()
        if not self._initialized:
            await self.authenticate()
        if not self.can_handle_query(query):
            raise ProviderError(f"{self.name} cannot handle query: {query}", self.name)

        handler = self._handler_map.get(query.asset)
        if not handler:
            raise ProviderError(f"No handler for asset type {query.asset}", self.name)
        df = await handler(query)

        if df is None or df.empty:
            return DataResponse(
                data=[],
                metadata=ResponseMetadata(
                    total_records=0,
                    query_time_ms=0,
                    data_source=self.name,
                    cache_hit=False,
                ),
                source=ProviderInfo(name=self.name),
            )

        data_points = self._df_to_datapoints(df, query)
        end_time = asyncio.get_event_loop().time()

        return DataResponse(
            data=data_points,
            metadata=ResponseMetadata(
                total_records=len(data_points),
                query_time_ms=(end_time - start_time) * 1000,
                data_source=self.name,
            ),
            source=ProviderInfo(name=self.name),
        )

    async def _get_stock_data(self, query: DataQuery) -> pd.DataFrame:
        """Fetch stock data."""
        symbol = query.symbols[0]
        adjust = query.adjustment.value if query.adjustment else ""
        if adjust == "none":
            adjust = ""  # akshare uses empty string for no adjustment

        if query.market == MarketType.CN:
            return self._ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=query.start_date.strftime("%Y%m%d") if query.start_date else "19700101",
                end_date=query.end_date.strftime("%Y%m%d") if query.end_date else datetime.now().strftime("%Y%m%d"),
                adjust=adjust,
            )
        elif query.market == MarketType.US:
            return self._ak.stock_us_daily(symbol=symbol, adjust=adjust)
        elif query.market == MarketType.HK:
            return self._ak.stock_hk_daily(symbol=symbol, adjust=adjust)
        raise ProviderError(f"Unsupported market for stocks: {query.market}", self.name)

    async def _get_etf_data(self, query: DataQuery) -> pd.DataFrame:
        """Fetch ETF data."""
        symbol = query.symbols[0]
        return self._ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=query.start_date.strftime("%Y%m%d") if query.start_date else "19700101",
            end_date=query.end_date.strftime("%Y%m%d") if query.end_date else datetime.now().strftime("%Y%m%d"),
        )

    async def _get_fund_data(self, query: DataQuery) -> pd.DataFrame:
        """Fetch Fund data."""
        symbol = query.symbols[0]
        return self._ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")

    def _df_to_datapoints(self, df: pd.DataFrame, query: DataQuery) -> list[DataPoint]:
        """Convert pandas DataFrame to a list of DataPoint objects."""
        data_points = []

        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
            "净值日期": "date",
            "单位净值": "close",
            "累计净值": "accumulated_nav",
        }
        df = df.rename(columns=column_map)

        for _, row in df.iterrows():
            try:
                timestamp = pd.to_datetime(row["date"])

                # Filter by date range if start_date or end_date is provided
                if query.start_date and timestamp.date() < query.start_date:
                    continue
                if query.end_date and timestamp.date() > query.end_date:
                    continue

                datapoint_data = {
                    "symbol": query.symbols[0],
                    "market": query.market,
                    "timestamp": timestamp,
                    "provider": self.name,
                    "close_price": Decimal(str(row["close"])) if "close" in row and pd.notna(row["close"]) else None,
                }

                if all(k in df.columns for k in ["open", "high", "low", "volume"]):
                    datapoint_data.update(
                        {
                            "open_price": Decimal(str(row["open"])) if pd.notna(row["open"]) else None,
                            "high_price": Decimal(str(row["high"])) if pd.notna(row["high"]) else None,
                            "low_price": Decimal(str(row["low"])) if pd.notna(row["low"]) else None,
                            "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
                        }
                    )

                data_points.append(DataPoint(**datapoint_data))

            except (KeyError, ValueError, TypeError, ValidationError) as e:
                logger.warning(f"Skipping row for symbol {query.symbols[0]} due to parsing error: {e}")
                continue

        return data_points

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def get_real_time_quote(self, symbol: str, market: str = "cn") -> dict[str, Any] | None:
        """获取实时报价."""
        # This is a placeholder and should be implemented if needed.
        return None
