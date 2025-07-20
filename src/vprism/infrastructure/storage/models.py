"""数据库存储模型."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataRecord(BaseModel):
    """数据记录模型."""
    
    id: Optional[str] = None
    symbol: str
    asset_type: str
    market: Optional[str] = None
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    timeframe: Optional[str] = None
    provider: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ProviderRecord(BaseModel):
    """提供商记录模型."""
    
    id: Optional[str] = None
    name: str
    version: Optional[str] = None
    endpoint: Optional[str] = None
    status: str = "active"
    last_healthy: Optional[datetime] = None
    request_count: int = 0
    error_count: int = 0
    avg_response_time_ms: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    capabilities: Optional[Dict[str, Any]] = None


class CacheRecord(BaseModel):
    """缓存记录模型."""
    
    id: Optional[str] = None
    cache_key: str
    query_hash: str
    data_source: Optional[str] = None
    hit_count: int = 0
    last_access: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryRecord(BaseModel):
    """查询记录模型."""
    
    id: Optional[str] = None
    query_hash: str
    asset_type: str
    market: Optional[str] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    provider: Optional[str] = None
    status: str = "pending"
    request_time_ms: Optional[int] = None
    response_size: Optional[int] = None
    cache_hit: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None