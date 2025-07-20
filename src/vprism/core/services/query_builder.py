"""查询构建器模块."""

from datetime import date, datetime, timedelta
from typing import List, Union

from vprism.core.models import AssetType, DataQuery, MarketType, TimeFrame


class QueryBuilder:
    """链式查询构建器，支持流畅的API调用."""

    def __init__(self, service=None):
        """初始化查询构建器.

        Args:
            service: 数据服务实例（可选，用于向后兼容）
        """
        self._query = DataQuery(
            asset=AssetType.STOCK,
            market=MarketType.CN,
            symbols=[],
            timeframe=TimeFrame.DAY_1,
            start_date=datetime.now().date() - timedelta(days=30),
            end_date=datetime.now().date(),
        )
        self._service = service

    def asset(self, asset_type: Union[str, AssetType]) -> "QueryBuilder":
        """设置资产类型.

        Args:
            asset_type: 资产类型

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(asset_type, str):
            asset_type = AssetType(asset_type)
        self._query.asset = asset_type
        return self

    def market(self, market: Union[str, MarketType]) -> "QueryBuilder":
        """设置市场类型.

        Args:
            market: 市场类型

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(market, str):
            market = MarketType(market)
        self._query.market = market
        return self

    def symbols(self, symbols: Union[str, List[str]]) -> "QueryBuilder":
        """设置股票代码.

        Args:
            symbols: 股票代码或代码列表

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        self._query.symbols = symbols
        return self

    def start(self, start_date: Union[str, date]) -> "QueryBuilder":
        """设置开始日期.

        Args:
            start_date: 开始日期

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        self._query.start = start_date
        return self

    def end(self, end_date: Union[str, date]) -> "QueryBuilder":
        """设置结束日期.

        Args:
            end_date: 结束日期

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        self._query.end = end_date
        return self

    def timeframe(self, timeframe: Union[str, TimeFrame]) -> "QueryBuilder":
        """设置时间框架.

        Args:
            timeframe: 时间框架

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        if isinstance(timeframe, str):
            timeframe = TimeFrame(timeframe)
        self._query.timeframe = timeframe
        return self

    def period(self, period: str) -> "QueryBuilder":
        """设置时间周期（简化API）.

        Args:
            period: 时间周期（"1d", "1w", "1m", "3m", "1y", "max"）

        Returns:
            QueryBuilder: 当前实例，用于链式调用
        """
        end_date = datetime.now().date()
        period_mapping = {
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "1y": timedelta(days=365),
            "max": timedelta(days=3650),  # 10 years
        }

        start_date = end_date - period_mapping.get(period, timedelta(days=30))
        self._query.start = start_date
        self._query.end = end_date
        return self

    def build(self) -> DataQuery:
        """构建查询对象.

        Returns:
            DataQuery: 构建完成的查询对象
        """
        return self._query

    @property
    def query(self) -> DataQuery:
        """获取查询对象."""
        return self._query

    def __repr__(self) -> str:
        """字符串表示."""
        return f"QueryBuilder({self._query})"
