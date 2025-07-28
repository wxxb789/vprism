"""Response models for data and errors."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .base import DataPoint


class ResponseMetadata(BaseModel):
    """响应元数据模型."""

    total_records: int
    query_time_ms: float
    data_source: str
    cache_hit: bool = False


class ProviderInfo(BaseModel):
    """提供商信息模型."""

    name: str
    version: str | None = None
    endpoint: str | None = None
    last_updated: datetime | None = None


class DataResponse(BaseModel):
    """数据响应模型."""

    data: list[DataPoint]
    metadata: ResponseMetadata
    source: ProviderInfo
    cached: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseModel):
    """错误响应模型."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
