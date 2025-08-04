"""Base data models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from pydantic import ConfigDict as PydanticConfigDict


class DataPoint(BaseModel):
    """单个数据点模型."""

    symbol: str
    timestamp: datetime
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    model_config = PydanticConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={Decimal: str, datetime: lambda v: v.isoformat()},
    )


class Asset(BaseModel):
    """资产信息模型."""

    symbol: str
    name: str
    asset_type: str  # Using string instead of enum to avoid circular imports
    market: str  # Using string instead of enum
    currency: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
