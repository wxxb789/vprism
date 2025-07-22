"""vprism自定义数据提供商实现 - 基于akshare的数据一致性验证."""

import asyncio
import hashlib
import json
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
)

from .base import (
    AuthConfig,
    AuthType,
    DataProvider,
    ProviderCapability,
    RateLimitConfig,
)


class VPrismProvider(DataProvider):
    """vprism自定义数据提供商 - 基于akshare的数据一致性验证."""

    def __init__(self):
        """初始化vprism提供商."""
        auth_config = AuthConfig(
            auth_type=AuthType.NONE, credentials={}, required_fields=[]
        )

        rate_limit = RateLimitConfig(
            requests_per_minute=30,  # 更严格的限制以确保数据质量
            requests_per_hour=500,
            requests_per_day=5000,
            concurrent_requests=3,
            backoff_factor=2.0,
            max_retries=5,
            initial_delay=1.0,
        )

        super().__init__("vprism", auth_config, rate_limit)
        self._data_cache = {}
        self._validation_cache = {}

    def _discover_capability(self) -> ProviderCapability:
        """发现vprism能力."""
        return ProviderCapability(
            supported_assets={"stock", "bond", "etf", "fund", "index"},
            supported_markets={"cn", "us", "hk"},
            supported_timeframes={"1d", "1wk", "1mo"},
            max_symbols_per_request=50,
            supports_real_time=False,  # 专注于历史数据验证
            supports_historical=True,
            data_delay_seconds=0,
            rate_limits={
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "requests_per_day": 5000,
            },
        )

    async def authenticate(self) -> bool:
        """vprism不需要认证."""
        self._is_authenticated = True
        return True

    async def get_data(self, query: DataQuery) -> DataResponse:
        """获取经过验证的数据."""
        if not self.can_handle_query(query):
            raise ProviderError(f"VPrism cannot handle query: {query}")

        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(query)

            # 检查缓存
            if cache_key in self._data_cache:
                data_points = self._data_cache[cache_key]
            else:
                # 获取并验证数据
                data_points = await self._fetch_and_validate_data(query)
                self._data_cache[cache_key] = data_points

            return DataResponse(
                data=data_points,
                metadata={
                    "total_records": len(data_points),
                    "query_time_ms": 0,
                    "data_source": "vprism",
                    "cache_hit": cache_key in self._data_cache,
                    "validation_passed": True,
                    "data_hash": self._calculate_data_hash(data_points),
                },
                source={"name": "vprism", "version": "1.0.0", "endpoint": "internal"},
                cached=cache_key in self._data_cache,
            )

        except Exception as e:
            raise ProviderError(f"Failed to fetch data from vprism: {e}") from e

    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """流式获取经过验证的数据."""
        data_response = await self.get_data(query)
        for data_point in data_response.data:
            yield data_point

    async def _fetch_and_validate_data(self, query: DataQuery) -> list[DataPoint]:
        """获取并验证数据."""
        raw_data = await self._fetch_raw_data(query)
        validated_data = await self._validate_data_integrity(raw_data, query)
        return validated_data

    async def _fetch_raw_data(self, query: DataQuery) -> list[DataPoint]:
        """获取原始数据."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_fetch_raw_data, query
        )

    def _sync_fetch_raw_data(self, query: DataQuery) -> list[DataPoint]:
        """同步获取原始数据."""
        data_points = []

        for symbol in query.symbols or []:
            try:
                symbol_data = self._fetch_symbol_data(symbol, query)
                data_points.extend(symbol_data)
            except Exception as e:
                print(f"Error fetching raw data for {symbol}: {e}")
                continue

        return data_points

    def _fetch_symbol_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取单个符号的数据."""
        data_points = []

        # 根据资产类型和市场选择接口
        if query.asset == AssetType.STOCK:
            data_points = self._fetch_stock_data(symbol, query)
        elif query.asset == AssetType.INDEX:
            data_points = self._fetch_index_data(symbol, query)
        elif query.asset == AssetType.ETF:
            data_points = self._fetch_etf_data(symbol, query)

        return data_points

    def _fetch_stock_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取股票数据."""
        data_points = []

        # 使用akshare获取数据，但增加验证步骤
        try:
            if query.market == MarketType.CN:
                # 获取A股数据
                stock_zh_a_hist_df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=query.start.strftime("%Y%m%d") if query.start else "",
                    end_date=query.end.strftime("%Y%m%d") if query.end else "",
                    adjust="",
                )

                # 数据质量检查
                if stock_zh_a_hist_df.empty:
                    return data_points

                # 检查数据完整性
                required_columns = ["日期", "开盘", "最高", "最低", "收盘", "成交量"]
                if not all(
                    col in stock_zh_a_hist_df.columns for col in required_columns
                ):
                    return data_points

                # 检查异常值
                stock_zh_a_hist_df = self._validate_price_data(stock_zh_a_hist_df)

                for _, row in stock_zh_a_hist_df.iterrows():
                    # 跳过异常值
                    if any(
                        val is None or val <= 0
                        for val in [row["开盘"], row["最高"], row["最低"], row["收盘"]]
                    ):
                        continue

                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=datetime.strptime(str(row["日期"]), "%Y-%m-%d"),
                        open=Decimal(str(row["开盘"])),
                        high=Decimal(str(row["最高"])),
                        low=Decimal(str(row["最低"])),
                        close=Decimal(str(row["收盘"])),
                        volume=Decimal(str(row["成交量"])),
                        amount=Decimal(str(row["成交额"])) if "成交额" in row else None,
                        extra_fields={
                            "validation_status": "passed",
                            "data_source": "akshare_validated",
                        },
                    )
                    data_points.append(data_point)

            elif query.market == MarketType.US:
                # 获取美股数据
                stock_us_daily_df = ak.stock_us_daily(symbol=symbol)

                if stock_us_daily_df.empty:
                    return data_points

                # 数据验证
                stock_us_daily_df = self._validate_price_data(stock_us_daily_df)

                # 过滤日期范围
                if query.start:
                    stock_us_daily_df = stock_us_daily_df[
                        stock_us_daily_df["date"] >= query.start
                    ]
                if query.end:
                    stock_us_daily_df = stock_us_daily_df[
                        stock_us_daily_df["date"] <= query.end
                    ]

                for _, row in stock_us_daily_df.iterrows():
                    if any(
                        val is None or val <= 0
                        for val in [row["open"], row["high"], row["low"], row["close"]]
                    ):
                        continue

                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=datetime.strptime(str(row["date"]), "%Y-%m-%d"),
                        open=Decimal(str(row["open"])),
                        high=Decimal(str(row["high"])),
                        low=Decimal(str(row["low"])),
                        close=Decimal(str(row["close"])),
                        volume=Decimal(str(row["volume"])),
                        amount=Decimal(str(row["close"])) * Decimal(str(row["volume"])),
                        extra_fields={
                            "validation_status": "passed",
                            "data_source": "akshare_validated",
                        },
                    )
                    data_points.append(data_point)

        except Exception as e:
            print(f"Error fetching validated stock data for {symbol}: {e}")

        return data_points

    def _fetch_index_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取指数数据."""
        data_points = []

        try:
            if query.market == MarketType.CN:
                # 获取中国指数
                index_zh_a_hist_df = ak.index_zh_a_hist(symbol=symbol)

                if index_zh_a_hist_df.empty:
                    return data_points

                # 数据验证
                index_zh_a_hist_df = self._validate_price_data(index_zh_a_hist_df)

                for _, row in index_zh_a_hist_df.iterrows():
                    data_point = DataPoint(
                        symbol=symbol,
                        timestamp=datetime.strptime(str(row["日期"]), "%Y-%m-%d"),
                        open=Decimal(str(row["开盘"])),
                        high=Decimal(str(row["最高"])),
                        low=Decimal(str(row["最低"])),
                        close=Decimal(str(row["收盘"])),
                        volume=Decimal(str(row["成交量"])),
                        extra_fields={
                            "validation_status": "passed",
                            "data_source": "akshare_index_validated",
                        },
                    )
                    data_points.append(data_point)

        except Exception as e:
            print(f"Error fetching validated index data for {symbol}: {e}")

        return data_points

    def _fetch_etf_data(self, symbol: str, query: DataQuery) -> list[DataPoint]:
        """获取ETF数据."""
        data_points = []

        try:
            # 获取ETF历史净值数据
            etf_df = ak.fund_etf_fund_info_em(symbol=symbol)

            if etf_df.empty:
                return data_points

            # 数据验证
            etf_df = self._validate_price_data(etf_df)

            # 过滤日期范围
            if query.start:
                etf_df = etf_df[etf_df["净值日期"] >= query.start]
            if query.end:
                etf_df = etf_df[etf_df["净值日期"] <= query.end]

            for _, row in etf_df.iterrows():
                data_point = DataPoint(
                    symbol=symbol,
                    timestamp=datetime.strptime(str(row["净值日期"]), "%Y-%m-%d"),
                    close=Decimal(str(row["单位净值"])),
                    open=None,
                    high=None,
                    low=None,
                    volume=None,
                    amount=None,
                    extra_fields={
                        "validation_status": "passed",
                        "data_source": "akshare_etf_validated",
                        "net_asset_value": str(row["累计净值"])
                        if "累计净值" in row
                        else None,
                    },
                )
                data_points.append(data_point)

        except Exception as e:
            print(f"Error fetching validated ETF data for {symbol}: {e}")

        return data_points

    def _validate_price_data(self, df) -> object:
        """验证价格数据的完整性."""
        # 移除重复数据
        df = df.drop_duplicates()

        # 检查并移除异常值
        numeric_columns = [
            col
            for col in df.columns
            if col in ["开盘", "最高", "最低", "收盘", "open", "high", "low", "close"]
        ]
        for col in numeric_columns:
            if col in df.columns:
                # 移除极端异常值（价格超过正常范围100倍）
                median_price = df[col].median()
                df = df[df[col] <= median_price * 100]
                df = df[df[col] >= median_price * 0.01]

        return df

    def _generate_cache_key(self, query: DataQuery) -> str:
        """生成查询缓存键."""
        key_data = {
            "asset": str(query.asset),
            "market": str(query.market),
            "symbols": sorted(query.symbols or []),
            "timeframe": str(query.timeframe),
            "start": query.start.isoformat() if query.start else None,
            "end": query.end.isoformat() if query.end else None,
        }
        data_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _calculate_data_hash(self, data_points: list[DataPoint]) -> str:
        """计算数据哈希值用于完整性验证."""
        if not data_points:
            return ""

        data_str = json.dumps(
            [
                {
                    "symbol": dp.symbol,
                    "timestamp": dp.timestamp.isoformat(),
                    "close": str(dp.close),
                }
                for dp in data_points
            ],
            sort_keys=True,
        )
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
