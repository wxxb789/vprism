"""
Core domain models for vprism financial data platform.

This module defines the fundamental data structures used throughout the platform,
including assets, data points, queries, and responses. All models use Pydantic
for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer


class AssetType(str, Enum):
    """Enumeration of supported asset types."""

    STOCK = "stock"
    BOND = "bond"
    ETF = "etf"
    FUND = "fund"
    FUTURES = "futures"
    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"
    INDEX = "index"
    COMMODITY = "commodity"
    WARRANT = "warrant"
    CONVERTIBLE = "convertible"
    REPO = "repo"
    MONEY_MARKET = "money_market"
    STRUCTURED = "structured"


class MarketType(str, Enum):
    """Enumeration of supported market types."""

    CN = "cn"  # China
    US = "us"  # United States
    HK = "hk"  # Hong Kong
    EU = "eu"  # Europe
    JP = "jp"  # Japan
    KR = "kr"  # South Korea
    SG = "sg"  # Singapore
    AU = "au"  # Australia
    IN = "in"  # India
    GLOBAL = "global"


class TimeFrame(str, Enum):
    """Enumeration of supported time frames."""

    TICK = "tick"
    SECOND_1 = "1s"
    SECOND_5 = "5s"
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"
    QUARTER_1 = "1Q"
    YEAR_1 = "1Y"


class DataPoint(BaseModel):
    """
    Represents a single financial data point.

    This is the fundamental unit of financial data in vprism, containing
    standard OHLCV data plus extensible metadata fields.
    """

    symbol: str = Field(..., description="Financial instrument symbol")
    timestamp: datetime = Field(..., description="Data point timestamp")
    open: Decimal | None = Field(None, description="Opening price")
    high: Decimal | None = Field(None, description="Highest price")
    low: Decimal | None = Field(None, description="Lowest price")
    close: Decimal | None = Field(None, description="Closing price")
    volume: Decimal | None = Field(None, description="Trading volume")
    amount: Decimal | None = Field(None, description="Trading amount/turnover")
    extra_fields: dict[str, Any] = Field(
        default_factory=dict, description="Additional provider-specific fields"
    )

    model_config = ConfigDict(
        validate_assignment=True,
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Validate timestamp is not in the future."""
        # Get current time with same timezone awareness as input
        now = datetime.now(timezone.utc) if v.tzinfo else datetime.now()
        if v > now:
            raise ValueError("Timestamp cannot be in the future")
        return v

    @field_serializer(
        "open", "high", "low", "close", "volume", "amount", when_used="json"
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        """Serialize Decimal fields to string for JSON."""
        return str(value) if value is not None else None

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize timestamp to ISO format for JSON."""
        return value.isoformat()


class Asset(BaseModel):
    """
    Represents a financial asset with metadata.

    Contains comprehensive information about a financial instrument,
    including classification, market information, and metadata.
    """

    symbol: str = Field(..., description="Asset symbol/ticker")
    name: str = Field(..., description="Asset full name")
    asset_type: AssetType = Field(..., description="Type of asset")
    market: MarketType = Field(..., description="Primary market")
    currency: str = Field(..., description="Base currency (ISO 4217)")
    exchange: str | None = Field(None, description="Primary exchange")
    sector: str | None = Field(None, description="Industry sector")
    industry: str | None = Field(None, description="Specific industry")
    country: str | None = Field(None, description="Country of origin")
    isin: str | None = Field(
        None, description="International Securities Identification Number"
    )
    cusip: str | None = Field(
        None, description="Committee on Uniform Securities Identification Procedures"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional asset metadata"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.strip().upper()

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code format."""
        if len(v) != 3:
            raise ValueError("Currency must be 3-character ISO 4217 code")
        return v.upper()


class DataQuery(BaseModel):
    """
    Represents a query for financial data.

    This is the primary interface for requesting data from vprism,
    supporting flexible parameter combinations for different use cases.
    """

    asset: AssetType = Field(..., description="Type of asset to query")
    market: MarketType | None = Field(None, description="Market to query")
    symbols: list[str] | None = Field(None, description="Specific symbols to query")
    provider: str | None = Field(None, description="Preferred data provider")
    timeframe: TimeFrame | None = Field(None, description="Data timeframe")
    start: datetime | None = Field(None, description="Start date/time")
    end: datetime | None = Field(None, description="End date/time")
    limit: int | None = Field(
        None, ge=1, le=10000, description="Maximum number of records"
    )
    fields: list[str] | None = Field(None, description="Specific fields to return")
    filters: dict[str, Any] = Field(
        default_factory=dict, description="Additional query filters"
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str] | None) -> list[str] | None:
        """Validate and normalize symbols."""
        if v is None:
            return v
        if not v:
            raise ValueError("Symbols list cannot be empty if provided")
        cleaned_symbols = [s.strip().upper() for s in v if s.strip()]
        if not cleaned_symbols:
            raise ValueError("Symbols list cannot be empty if provided")
        return cleaned_symbols

    @field_validator("start", "end")
    @classmethod
    def validate_dates(cls, v: datetime | None) -> datetime | None:
        """Validate date ranges."""
        if v:
            # Get current time with same timezone awareness as input
            now = datetime.now(timezone.utc) if v.tzinfo else datetime.now()
            if v > now:
                raise ValueError("Query dates cannot be in the future")
        return v

    def cache_key(self) -> str:
        """Generate a cache key for this query."""
        key_parts = [
            f"asset:{self.asset.value}",
            f"market:{self.market.value}" if self.market else "",
            f"symbols:{','.join(sorted(self.symbols))}" if self.symbols else "",
            f"provider:{self.provider}" if self.provider else "",
            f"timeframe:{self.timeframe.value}" if self.timeframe else "",
            f"start:{self.start.isoformat()}" if self.start else "",
            f"end:{self.end.isoformat()}" if self.end else "",
            f"limit:{self.limit}" if self.limit else "",
        ]
        return "|".join(filter(None, key_parts))


class ProviderInfo(BaseModel):
    """Information about a data provider."""

    name: str = Field(..., description="Provider name")
    version: str | None = Field(None, description="Provider version")
    url: str | None = Field(None, description="Provider URL")
    rate_limit: int | None = Field(None, description="Requests per minute limit")
    cost: str | None = Field(None, description="Cost tier (free/paid/premium)")


class ResponseMetadata(BaseModel):
    """Metadata about a data response."""

    query_time: datetime = Field(
        default_factory=datetime.now, description="Query execution time"
    )
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    record_count: int = Field(..., description="Number of records returned")
    cache_hit: bool = Field(False, description="Whether data was served from cache")
    data_quality_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Data quality score (0-1)"
    )
    warnings: list[str] = Field(default_factory=list, description="Query warnings")


class DataResponse(BaseModel):
    """
    Response containing financial data and metadata.

    This is the standard response format for all data queries in vprism,
    providing both the requested data and comprehensive metadata.
    """

    data: list[DataPoint] = Field(..., description="The requested financial data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    source: ProviderInfo = Field(..., description="Data source information")
    query: DataQuery = Field(..., description="Original query")

    @property
    def is_empty(self) -> bool:
        """Check if response contains no data."""
        return len(self.data) == 0

    @property
    def symbols(self) -> list[str]:
        """Get unique symbols in the response."""
        return list({point.symbol for point in self.data})

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        """Get the date range of the data."""
        if not self.data:
            raise ValueError("Cannot get date range from empty response")

        timestamps = [point.timestamp for point in self.data]
        return min(timestamps), max(timestamps)
