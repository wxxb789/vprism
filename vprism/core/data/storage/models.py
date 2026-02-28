"""Database storage models - unified data representations."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from vprism.core.models import DataPoint
from vprism.core.models.market import MarketType


class OHLCVRecord(BaseModel):
    """Unified OHLCV record - maps directly to the ohlcv table.

    Uses Decimal for price fields and timezone-aware timestamps.
    """

    model_config = {"frozen": True}

    symbol: str
    market: str
    ts: datetime
    timeframe: str
    provider: str
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    amount: Decimal | None = None
    batch_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_data_point(self) -> DataPoint:
        """Convert OHLCVRecord to DataPoint."""
        return DataPoint(
            symbol=self.symbol,
            timestamp=self.ts,
            open_price=self.open,
            high_price=self.high,
            low_price=self.low,
            close_price=self.close,
            volume=Decimal(str(self.volume)) if self.volume is not None else None,
            amount=self.amount,
            market=MarketType(self.market) if self.market else MarketType.CN,
            provider=self.provider,
        )

    @classmethod
    def from_data_point(cls, dp: DataPoint, provider: str, timeframe: str = "1d") -> "OHLCVRecord":
        """Create OHLCVRecord from a DataPoint."""
        return cls(
            symbol=dp.symbol,
            market=dp.market.value if dp.market else "cn",
            ts=dp.timestamp,
            timeframe=timeframe,
            provider=provider,
            open=dp.open_price,
            high=dp.high_price,
            low=dp.low_price,
            close=dp.close_price,
            volume=int(dp.volume) if dp.volume is not None else None,
            amount=dp.amount,
        )
