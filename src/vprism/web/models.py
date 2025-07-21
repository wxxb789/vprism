"""
Web API 数据模型
定义 FastAPI 的请求/响应模型
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from vprism.core.models import Asset, DataQuery, DataResponse, MarketType, TimeFrame


class APIResponse(BaseModel):
    """标准 API 响应格式"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[Any] = Field(None, description="响应数据")
    message: Optional[str] = Field(None, description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间戳")
    request_id: Optional[str] = Field(None, description="请求ID，用于追踪")


class ErrorResponse(BaseModel):
    """错误响应格式"""
    success: bool = Field(False, description="请求失败")
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="详细错误信息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="错误时间戳")
    request_id: Optional[str] = Field(None, description="请求ID，用于追踪")


class StockDataRequest(BaseModel):
    """股票数据请求模型"""
    symbol: str = Field(..., description="股票代码，如 AAPL, 000001")
    market: MarketType = Field(MarketType.US, description="市场类型")
    timeframe: TimeFrame = Field(TimeFrame.DAY_1, description="时间周期")
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")
    limit: Optional[int] = Field(100, ge=1, le=10000, description="返回数据条数限制")


class MarketDataRequest(BaseModel):
    """市场数据请求模型"""
    market: MarketType = Field(..., description="市场类型")
    timeframe: TimeFrame = Field(TimeFrame.DAY_1, description="时间周期")
    symbols: Optional[List[str]] = Field(None, description="股票代码列表，为空时获取整个市场")
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")


class BatchDataRequest(BaseModel):
    """批量数据请求模型"""
    queries: List[StockDataRequest] = Field(..., min_items=1, max_items=100, description="查询列表")
    async_processing: bool = Field(False, description="是否异步处理")


class HealthStatus(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="系统状态")
    version: str = Field(..., description="系统版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="检查时间戳")
    components: Dict[str, str] = Field(..., description="各组件状态")


class ProviderStatus(BaseModel):
    """数据提供商状态"""
    name: str = Field(..., description="提供商名称")
    status: str = Field(..., description="状态 (healthy, degraded, unavailable)")
    last_check: datetime = Field(..., description="最后检查时间")
    response_time: Optional[float] = Field(None, description="平均响应时间(ms)")
    success_rate: Optional[float] = Field(None, description="成功率(0-1)")


class CacheStats(BaseModel):
    """缓存统计信息"""
    hits: int = Field(..., description="缓存命中次数")
    misses: int = Field(..., description="缓存未命中次数")
    hit_rate: float = Field(..., description="缓存命中率")
    size: int = Field(..., description="缓存条目数")
    memory_usage: Optional[str] = Field(None, description="内存使用量")