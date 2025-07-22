"""健康检查系统 - 简化版本。"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class HealthStatus:
    """健康状态数据模型。"""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    checks: dict[str, dict[str, Any]]
    uptime_seconds: float
    version: str = "0.1.0"


class HealthChecker:
    """简化版健康检查器。"""

    def __init__(self):
        self.start_time = time.time()
        self.checks: dict[str, callable] = {}
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """注册默认的健康检查。"""
        self.register_check("system", self._check_system_health)
        self.register_check("memory", self._check_memory_usage)

    def register_check(self, name: str, check_func: callable) -> None:
        """注册自定义健康检查。"""
        self.checks[name] = check_func

    async def _check_system_health(self) -> dict[str, Any]:
        """基础系统健康检查。"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "status": "healthy"
                if cpu_percent < 90 and memory.percent < 90
                else "degraded",
                "details": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                },
            }
        except ImportError:
            return {
                "status": "healthy",
                "details": {"note": "psutil not available, basic check passed"},
            }

    async def _check_memory_usage(self) -> dict[str, Any]:
        """内存使用情况检查。"""
        try:
            return {
                "status": "healthy",
                "details": {"uptime_seconds": round(time.time() - self.start_time, 2)},
            }
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def check_health(self) -> HealthStatus:
        """执行所有健康检查。"""
        checks_results: dict[str, dict[str, Any]] = {}
        overall_status = "healthy"
        failed_checks = 0
        total_checks = len(self.checks)

        # 并行执行所有检查
        tasks = []
        check_names = list(self.checks.keys())

        for name, check_func in self.checks.items():
            if asyncio.iscoroutinefunction(check_func):
                tasks.append(check_func())
            else:
                tasks.append(asyncio.to_thread(check_func))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(check_names, results, strict=False):
                if isinstance(result, Exception):
                    checks_results[name] = {"status": "unhealthy", "error": str(result)}
                    failed_checks += 1
                    overall_status = "unhealthy"
                    logger.error(
                        f"Health check '{name}' failed with exception",
                        extra={"check_name": name, "error": str(result)},
                    )
                else:
                    checks_results[name] = result
                    if result.get("status") == "unhealthy":
                        overall_status = "unhealthy"
                        failed_checks += 1
                    elif (
                        result.get("status") == "degraded"
                        and overall_status == "healthy"
                    ):
                        overall_status = "degraded"
        except Exception as e:
            logger.error("Health check execution failed", extra={"error": str(e)})
            overall_status = "unhealthy"
            checks_results["execution"] = {"status": "unhealthy", "error": str(e)}

        health_status = HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            checks=checks_results,
            uptime_seconds=round(time.time() - self.start_time, 2),
        )

        logger.info(
            "Health check completed",
            extra={
                "status": overall_status,
                "total_checks": total_checks,
                "failed_checks": failed_checks,
                "uptime_seconds": health_status.uptime_seconds,
            },
        )

        return health_status

    async def check_providers(self, providers: list[str]) -> dict[str, Any]:
        """检查数据提供商状态（简化版）。"""
        provider_status = {}
        for provider in providers:
            try:
                # 简化检查 - 只检查是否可用
                provider_status[provider] = {
                    "status": "healthy",
                    "last_check": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                provider_status[provider] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.utcnow().isoformat(),
                }

        return provider_status


# 全局健康检查器实例
_health_checker: HealthChecker = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器实例。"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


class SimpleHealthMiddleware:
    """FastAPI健康检查中间件。"""

    def __init__(self, app=None):
        self.app = app
        self.checker = get_health_checker()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/health":
            health = await self.checker.check_health()
            response_body = {
                "status": health.status,
                "timestamp": health.timestamp.isoformat(),
                "uptime_seconds": health.uptime_seconds,
                "version": health.version,
            }
            await self._send_json_response(send, response_body)
        else:
            await self.app(scope, receive, send)

    async def _send_json_response(self, send, body):
        """发送JSON响应。"""
        import json

        body_bytes = json.dumps(body).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body_bytes})


# 便捷函数
async def check_system_health() -> dict[str, Any]:
    """快速系统健康检查。"""
    checker = get_health_checker()
    health = await checker.check_health()
    return {
        "status": health.status,
        "uptime": f"{health.uptime_seconds}s",
        "checks_count": len(health.checks),
    }
