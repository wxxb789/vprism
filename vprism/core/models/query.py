"""Query models and builders."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from vprism.core.models.market import AssetType, MarketType, TimeFrame


class Adjustment(str, Enum):
    """Price adjustment type."""

    NONE = "none"
    FORWARD = "qfq"
    BACKWARD = "hfq"


class DataQuery(BaseModel):
    """数据查询模型."""

    asset: AssetType
    market: MarketType | None = None
    provider: str | None = None
    timeframe: TimeFrame = TimeFrame.DAY_1  # 默认日线
    start: datetime | None = None
    end: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    symbols: list[str] | None = None
    raw_symbols: list[str] | None = None
    adjustment: Adjustment | None = Field(default=Adjustment.NONE, description="Price adjustment type")


class QueryBuilder:
    """查询构建器 - 简化版."""

    def __init__(self) -> None:
        self._query: dict[str, Any] = {}

    def asset_type(self, asset_type: AssetType) -> "QueryBuilder":
        """设置资产类型."""
        self._query["asset"] = asset_type
        return self

    def market(self, market: MarketType) -> "QueryBuilder":
        """设置市场类型."""
        self._query["market"] = market
        return self

    def provider(self, provider: str) -> "QueryBuilder":
        """设置数据提供商."""
        self._query["provider"] = provider
        return self

    def timeframe(self, timeframe: TimeFrame) -> "QueryBuilder":
        """设置时间框架."""
        self._query["timeframe"] = timeframe
        return self

    def symbols(self, symbols: list[str]) -> "QueryBuilder":
        """设置股票代码列表."""
        self._query["symbols"] = symbols
        return self

    def with_adjustment(self, adjustment: Adjustment) -> "QueryBuilder":
        """Set the price adjustment type."""
        self._query["adjustment"] = adjustment
        return self

    def date_range(self, start: datetime | date, end: datetime | date) -> "QueryBuilder":
        """设置日期范围."""
        if isinstance(start, datetime):
            self._query["start"] = start
        else:
            self._query["start_date"] = start

        if isinstance(end, datetime):
            self._query["end"] = end
        else:
            self._query["end_date"] = end
        return self

    def build(self) -> DataQuery:
        """构建查询对象."""
        return DataQuery(**self._query)
