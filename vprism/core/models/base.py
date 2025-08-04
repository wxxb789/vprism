"""Base data models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_serializer
from pydantic import ConfigDict as PydanticConfigDict

from .market import MarketType


class DataPoint(BaseModel):
    """单个数据点模型."""

    symbol: str
    market: MarketType
    timestamp: datetime
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    close_price: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    provider: str | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    model_config = PydanticConfigDict(
        arbitrary_types_allowed=True,
    )

    @field_serializer("open_price", "high_price", "low_price", "close_price", "volume", "amount", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        """Serialize Decimal to string."""
        if value is None:
            return None
        return str(value)

    @field_serializer("timestamp", when_used="json")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to isoformat string."""
        return value.isoformat()


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
