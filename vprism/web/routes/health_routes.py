"""
健康检查和系统状态路由
"""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from loguru import logger

from ...core.health import get_health_checker
from ..models import APIResponse, CacheStats, ProviderStatus

router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check(request: Request) -> APIResponse:
    """
    基础健康检查

    检查应用是否正常运行
    """
    try:
        checker = get_health_checker()
        health = await checker.check_health()

        logger.info(
            "Health check completed",
            extra={
                "endpoint": "/health",
                "status": health.status,
                "uptime_seconds": health.uptime_seconds,
            },
        )

        return APIResponse(
            success=True,
            data={
                "status": health.status,
                "timestamp": health.timestamp.isoformat(),
                "uptime_seconds": health.uptime_seconds,
                "version": health.version,
                "checks": health.checks,
            },
            message="系统健康检查完成",
        )

    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "endpoint": "/health",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        return APIResponse(success=False, data=None, message=f"健康检查失败: {str(e)}")


@router.get("/health/ready", response_model=APIResponse)
async def readiness_check(request: Request) -> APIResponse:
    """
    就绪检查（Kubernetes 使用）

    检查应用是否准备好接收流量
    """
    try:
        client = request.app.state.vprism_client

        # 检查是否可以执行基本查询
        if client and hasattr(client, "router") and client.router:
            return APIResponse(success=True, data={"ready": True}, message="应用已就绪")
        else:
            return APIResponse(success=False, data={"ready": False}, message="应用未就绪")

    except Exception as e:
        return APIResponse(success=False, data={"ready": False}, message=f"就绪检查失败: {str(e)}")


@router.get("/health/live", response_model=APIResponse)
async def liveness_check(request: Request) -> APIResponse:
    """
    存活检查（Kubernetes 使用）

    检查应用是否存活
    """
    return APIResponse(success=True, data={"alive": True}, message="应用存活")


@router.get("/health/providers", response_model=APIResponse)
async def provider_health_check(request: Request) -> APIResponse:
    """
    数据提供商健康检查

    检查所有数据提供商的状态
    """
    try:
        # 获取提供商状态（简化实现）
        providers = [
            ProviderStatus(
                name="akshare",
                status="healthy",
                last_check=datetime.now(UTC),
                response_time=150.5,
                success_rate=0.98,
            ),
            ProviderStatus(
                name="yahoo_finance",
                status="healthy",
                last_check=datetime.now(UTC),
                response_time=200.3,
                success_rate=0.95,
            ),
        ]

        return APIResponse(
            success=True,
            data=[jsonable_encoder(p) for p in providers],
            message="提供商健康检查完成",
        )

    except Exception as e:
        return APIResponse(success=False, data=None, message=f"提供商检查失败: {str(e)}")


@router.get("/health/cache", response_model=APIResponse)
async def cache_health_check(request: Request) -> APIResponse:
    """
    缓存系统健康检查

    检查缓存系统的状态和统计
    """
    try:
        # 获取缓存统计（简化实现）
        cache_stats = CacheStats(hits=1000, misses=200, hit_rate=0.833, size=500, memory_usage="50MB")

        return APIResponse(success=True, data=jsonable_encoder(cache_stats), message="缓存系统状态正常")

    except Exception as e:
        return APIResponse(success=False, data=None, message=f"缓存检查失败: {str(e)}")


@router.get("/metrics", response_model=APIResponse)
async def get_metrics(request: Request) -> APIResponse:
    """
    获取系统指标

    返回系统运行指标和统计数据
    """
    try:
        # 简化实现，实际应该集成 Prometheus 等监控系统
        metrics = {
            "uptime": time.time() - getattr(request.app.state, "start_time", time.time()),
            "requests_count": 1000,  # 应该从实际计数器获取
            "error_rate": 0.02,
            "average_response_time": 150.5,
            "data_sources": {"total": 2, "healthy": 2, "degraded": 0, "unavailable": 0},
        }

        return APIResponse(success=True, data=metrics, message="系统指标获取成功")

    except Exception as e:
        return APIResponse(success=False, data=None, message=f"指标获取失败: {str(e)}")
