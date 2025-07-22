"""统一的日志系统，使用loguru实现结构化日志记录。"""

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel


class LogConfig(BaseModel):
    """日志配置模型。"""

    level: str = "INFO"
    format: str = "json"  # json or console
    console_output: bool = True
    file_output: bool = False
    file_path: str | None = None
    rotation: str = "10 MB"
    retention: str = "30 days"
    compression: str = "zip"


class StructuredLogger:
    """vprism统一日志系统。"""

    def __init__(self, config: LogConfig | None = None):
        self.config = config or LogConfig()
        self.logger = logger
        self._setup_logger()

    def _setup_logger(self) -> None:
        """配置loguru日志器。"""
        # 清除默认处理器
        self.logger.remove()

        if self.config.console_output:
            self._setup_console_handler()

        if self.config.file_output and self.config.file_path:
            self._setup_file_handler()

    def _setup_console_handler(self) -> None:
        """设置控制台输出处理器。"""
        if self.config.format == "json":
            self.logger.add(
                sys.stderr,
                level=self.config.level,
                format=self._json_formatter,
                serialize=True,
            )
        else:
            self.logger.add(
                sys.stderr,
                level=self.config.level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8>}</level> | "
                "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
            )

    def _setup_file_handler(self) -> None:
        """设置文件输出处理器。"""
        log_file = Path(self.config.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=self.config.level,
            format=self._json_formatter,
            serialize=True,
            rotation=self.config.rotation,
            retention=self.config.retention,
            compression=self.config.compression,
        )

    def _json_formatter(self, record: dict[str, Any]) -> str:
        """JSON格式化器。"""
        log_data = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "thread": record["thread"].name if record.get("thread") else None,
            "process": record["process"].name if record.get("process") else None,
        }

        # 添加额外字段 - 处理嵌套的extra结构
        if record.get("extra"):
            # 移除可能的嵌套extra
            extra_data = record["extra"]
            if isinstance(extra_data, dict) and "extra" in extra_data:
                extra_data = extra_data["extra"]
            log_data.update(extra_data)

        return json.dumps(log_data, ensure_ascii=False, default=str)

    def configure(self, **kwargs: Any) -> None:
        """动态更新日志配置。"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._setup_logger()


# 全局日志实例
_global_logger: StructuredLogger | None = None


def get_logger() -> StructuredLogger:
    """获取全局日志实例。"""
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger()
    return _global_logger


def configure_logging(**kwargs: Any) -> None:
    """配置全局日志系统。"""
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger(LogConfig(**kwargs))
    else:
        _global_logger.configure(**kwargs)


# 便捷函数，保持向后兼容
logger = logger


def bind(**kwargs: Any) -> Any:
    """绑定上下文到日志器。"""
    return logger.bind(**kwargs)


def log_with_context(level: str, message: str, **context: Any) -> None:
    """带上下文的日志记录。"""
    logger.opt(depth=1).log(level, message, **context)


class PerformanceLogger:
    """性能日志装饰器。"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            import time

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000
                logger.success(
                    f"{self.operation_name} completed",
                    extra={
                        "duration_ms": round(duration, 2),
                        "operation": self.operation_name,
                        "status": "success",
                    },
                )
                return result
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{self.operation_name} failed",
                    extra={
                        "duration_ms": round(duration, 2),
                        "operation": self.operation_name,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                raise

        return wrapper


class RequestLogger:
    """HTTP请求日志中间件。"""

    def __init__(self, exclude_paths: list | None = None):
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

    def __call__(self, app):
        async def middleware(scope, receive, send):
            if scope["type"] != "http":
                await app(scope, receive, send)
                return

            import time

            from starlette.requests import Request

            request = Request(scope, receive)
            path = request.url.path

            if any(exclude in path for exclude in self.exclude_paths):
                await app(scope, receive, send)
                return

            start_time = time.time()
            logger.info(
                "Request started",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "client": f"{request.client.host}:{request.client.port}"
                    if request.client
                    else None,
                    "user_agent": request.headers.get("user-agent", "unknown"),
                },
            )

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    duration = (time.time() - start_time) * 1000
                    logger.success(
                        "Request completed",
                        extra={
                            "method": request.method,
                            "url": str(request.url),
                            "status_code": message["status"],
                            "duration_ms": round(duration, 2),
                        },
                    )
                await send(message)

            await app(scope, receive, send_wrapper)

        return middleware


# 初始化默认日志配置
configure_logging()
