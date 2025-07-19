"""Core data models for vprism financial data."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import AssetType, DataQuality, MarketType, TimeFrame


class Asset(BaseModel):
    """Financial asset information."""

    symbol: str = Field(..., description="Asset symbol/ticker")
    name: str = Field(..., description="Asset full name")
    asset_type: AssetType = Field(..., description="Type of asset")
    market: MarketType = Field(..., description="Market where asset is traded")
    currency: str = Field(..., description="Currency denomination")
    exchange: Optional[str] = Field(None, description="Exchange symbol")
    sector: Optional[str] = Field(None, description="Business sector")
    industry: Optional[str] = Field(None, description="Industry classification")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        },
        use_enum_values=True,
    )


class DataPoint(BaseModel):
    """Single data point for financial data."""

    symbol: str = Field(..., description="Asset symbol")
    timestamp: datetime = Field(..., description="Data timestamp")
    open: Optional[Decimal] = Field(None, description="Open price")
    high: Optional[Decimal] = Field(None, description="High price")
    low: Optional[Decimal] = Field(None, description="Low price")
    close: Optional[Decimal] = Field(None, description="Close price")
    volume: Optional[Decimal] = Field(None, description="Trading volume")
    amount: Optional[Decimal] = Field(None, description="Trading amount")
    extra_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional fields")

    class Config:
        """Pydantic configuration."""
        
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class DataQuery(BaseModel):
    """Query parameters for data retrieval."""

    asset_type: AssetType = Field(..., description="Type of asset to query")
    market: Optional[MarketType] = Field(None, description="Market to query")
    symbols: List[str] = Field(default_factory=list, description="List of symbols to query")
    timeframe: Optional[TimeFrame] = Field(None, description="Time frame for data")
    start: Optional[datetime] = Field(None, description="Start date/time")
    end: Optional[datetime] = Field(None, description="End date/time")
    provider: Optional[str] = Field(None, description="Specific provider to use")

    class Config:
        """Pydantic configuration."""
        
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        use_enum_values = True


class ResponseMetadata(BaseModel):
    """Metadata for data response."""

    total_records: int = Field(0, description="Total number of records")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(100, description="Records per page")
    total_pages: int = Field(1, description="Total number of pages")
    has_next: bool = Field(False, description="Has next page")
    has_prev: bool = Field(False, description="Has previous page")
    quality: DataQuality = Field(DataQuality.UNKNOWN, description="Data quality level")
    processed_at: datetime = Field(default_factory=datetime.now, description="Processing timestamp")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
        use_enum_values=True,
    )


class ProviderInfo(BaseModel):
    """Information about data provider."""

    name: str = Field(..., description="Provider name/identifier")
    display_name: str = Field(..., description="Human-readable name")
    endpoint: Optional[str] = Field(None, description="API endpoint")
    version: Optional[str] = Field(None, description="API version")
    description: Optional[str] = Field(None, description="Provider description")


class DataResponse(BaseModel):
    """Response from data query."""

    data: List[DataPoint] = Field(default_factory=list, description="List of data points")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    provider: ProviderInfo = Field(..., description="Provider information")
    cached: bool = Field(False, description="Whether data is from cache")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        },
        use_enum_values=True,
    )