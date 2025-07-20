"""vprism客户端实现 - 提供简单和复杂的API接口"""

import asyncio
from typing import Any

from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame
from vprism.core.services.data_router import DataRouter
from vprism.infrastructure.providers.registry import ProviderRegistry


class QueryBuilder:
    """构建器模式API - 支持复杂查询构建"""

    def __init__(self):
        self._asset: AssetType | None = None
        self._market: MarketType | None = None
        self._symbols: list[str] | None = None
        self._timeframe: TimeFrame | None = None
        self._start: str | None = None
        self._end: str | None = None
        self._provider: str | None = None

    def asset(self, asset: str) -> "QueryBuilder":
        """设置资产类型"""
        self._asset = AssetType(asset)
        return self

    def market(self, market: str) -> "QueryBuilder":
        """设置市场"""
        self._market = MarketType(market)
        return self

    def symbols(self, symbols: list[str]) -> "QueryBuilder":
        """设置股票代码列表"""
        self._symbols = symbols
        return self

    def timeframe(self, timeframe: str) -> "QueryBuilder":
        """设置时间框架"""
        self._timeframe = TimeFrame(timeframe)
        return self

    def date_range(self, start: str, end: str) -> "QueryBuilder":
        """设置日期范围"""
        self._start = start
        self._end = end
        return self

    def provider(self, provider: str) -> "QueryBuilder":
        """设置数据提供商"""
        self._provider = provider
        return self

    def build(self) -> DataQuery:
        """构建最终的查询对象"""
        from datetime import datetime

        start_dt = None
        end_dt = None
        if self._start:
            start_dt = datetime.fromisoformat(self._start)
        if self._end:
            end_dt = datetime.fromisoformat(self._end)

        return DataQuery(
            asset=self._asset,
            market=self._market,
            symbols=self._symbols,
            timeframe=self._timeframe,
            start=start_dt,
            end=end_dt,
            provider=self._provider,
        )


class VPrismClient:
    """vprism主客户端"""

    def __init__(self):
        """初始化客户端"""
        self.registry = ProviderRegistry()
        self.router = DataRouter(self.registry)
        self._configured = False

    def configure(self, **config):
        """配置客户端"""
        self._configured = True
        # TODO: 实现配置逻辑

    def query(self) -> QueryBuilder:
        """获取查询构建器"""
        return QueryBuilder()

    async def execute(self, query: DataQuery) -> Any:
        """执行查询"""
        if not self._configured:
            # 使用默认配置
            pass

        provider = await self.router.route_query(query)
        return await provider.get_data(query)

    def get(
        self,
        asset: str = None,
        market: str = None,
        symbols: list[str] = None,
        timeframe: str = None,
        start: str = None,
        end: str = None,
        provider: str = None,
        **kwargs,
    ) -> Any:
        """简单API - 同步获取数据"""
        query = DataQuery(
            asset=AssetType(asset) if asset else None,
            market=MarketType(market) if market else None,
            symbols=symbols,
            timeframe=TimeFrame(timeframe) if timeframe else None,
            start=start,
            end=end,
            provider=provider,
        )

        # 在事件循环中运行异步方法
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.execute(query))
