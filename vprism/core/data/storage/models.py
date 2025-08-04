"""数据库存储模型."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DataRecord(BaseModel):
    """数据记录模型."""

    id: str | None = None
    symbol: str
    asset_type: str
    market: str | None = None
    timestamp: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    timeframe: str | None = None
    provider: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] | None = None


class ProviderRecord(BaseModel):
    """提供商记录模型."""

    id: str | None = None
    name: str
    version: str | None = None
    endpoint: str | None = None
    status: str = "active"
    last_healthy: datetime | None = None
    request_count: int = 0
    error_count: int = 0
    avg_response_time_ms: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    capabilities: dict[str, Any] | None = None


class CacheRecord(BaseModel):
    """缓存记录模型."""

    id: str | None = None
    cache_key: str
    query_hash: str
    data_source: str | None = None
    hit_count: int = 0
    last_access: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class QueryRecord(BaseModel):
    """查询记录模型."""

    id: str | None = None
    query_hash: str
    asset_type: str
    market: str | None = None
    symbols: list[str] | None = None
    timeframe: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    provider: str | None = None
    status: str = "pending"
    request_time_ms: int | None = None
    response_size: int | None = None
    cache_hit: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
