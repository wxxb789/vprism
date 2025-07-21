"""统一的日志系统，使用loguru实现结构化日志记录。"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from pydantic import BaseModel


class LogConfig(BaseModel):
    """日志配置模型。"""

    level: str = "INFO"
    format: str = "json"  # json or console
    console_output: bool = True
    file_output: bool = False
    file_path: Optional[str] = None
    rotation: str = "10 MB"
    retention: str = "30 days"
    compression: str = "zip"


class StructuredLogger:
    """vprism统一日志系统。"""

    def __init__(self, config: Optional[LogConfig] = None):
        self.config = config or LogConfig()
        self._setup_logger()

    def _setup_logger(self) -> None:
        """配置loguru日志器。"""
        # 清除默认处理器
        logger.remove()

        if self.config.console_output:
            self._setup_console_handler()

        if self.config.file_output and self.config.file_path:
            self._setup_file_handler()

    def _setup_console_handler(self) -> None:
        """设置控制台输出处理器。"""
        if self.config.format == "json":
            logger.add(
                sys.stderr,
                level=self.config.level,
                format=self._json_formatter,
                serialize=True,
            )
        else:
            logger.add(
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

    def _json_formatter(self, record: Dict[str, Any]) -> str:
        """JSON格式化器。"""
        log_data = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "thread": record["thread"].name,
            "process": record["process"].name,
        }

        # 添加额外字段
        if record["extra"]:
            log_data.update(record["extra"])

        return json.dumps(log_data, ensure_ascii=False)

    def configure(self, **kwargs: Any) -> None:
        """动态更新日志配置。"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._setup_logger()


# 全局日志实例
_global_logger: Optional[StructuredLogger] = None


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
            start_time = logger.time()
            try:
                result = await func(*args, **kwargs)
                duration = (logger.time() - start_time) * 1000
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
                duration = (logger.time() - start_time) * 1000
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

    def __init__(self, exclude_paths: Optional[list] = None):
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

    async def __call__(self, request, call_next):
        if any(path in str(request.url) for path in self.exclude_paths):
            response = await call_next(request)
            return response

        start_time = logger.time()
        logger.info(
            f"Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client": getattr(request, "client", None)
                and f"{request.client.host}:{request.client.port}",
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        )

        try:
            response = await call_next(request)
            duration = (logger.time() - start_time) * 1000
            logger.success(
                f"Request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "duration_ms": round(duration, 2),
                },
            )
            return response
        except Exception as e:
            duration = (logger.time() - start_time) * 1000
            logger.error(
                f"Request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "duration_ms": round(duration, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            raise


# 初始化默认日志配置
configure_logging()
