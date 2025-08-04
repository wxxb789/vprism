"""查询构建器实现."""

from datetime import datetime

from ..models.market import AssetType, MarketType, TimeFrame
from ..models.query import DataQuery


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
