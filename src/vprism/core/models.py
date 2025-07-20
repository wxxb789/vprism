"""核心数据模型和枚举类型."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    """资产类型枚举."""
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


class MarketType(str, Enum):
    """市场类型枚举."""
    CN = "cn"  # 中国
    US = "us"  # 美国
    HK = "hk"  # 香港
    EU = "eu"  # 欧洲
    JP = "jp"  # 日本
    GLOBAL = "global"


class TimeFrame(str, Enum):
    """时间框架枚举."""
    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class DataPoint(BaseModel):
    """单个数据点模型."""
    symbol: str
    timestamp: datetime
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    extra_fields: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        """Pydantic配置."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class Asset(BaseModel):
    """资产信息模型."""
    symbol: str
    name: str
    asset_type: AssetType
    market: MarketType
    currency: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataQuery(BaseModel):
    """数据查询模型."""
    asset: AssetType
    market: Optional[MarketType] = None
    provider: Optional[str] = None
    timeframe: Optional[TimeFrame] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    symbols: Optional[List[str]] = None


class ResponseMetadata(BaseModel):
    """响应元数据模型."""
    total_records: int
    query_time_ms: float
    data_source: str
    cache_hit: bool = False


class ProviderInfo(BaseModel):
    """提供商信息模型."""
    name: str
    version: Optional[str] = None
    endpoint: Optional[str] = None
    last_updated: Optional[datetime] = None


class DataResponse(BaseModel):
    """数据响应模型."""
    data: List[DataPoint]
    metadata: ResponseMetadata
    source: ProviderInfo
    cached: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """错误响应模型."""
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)