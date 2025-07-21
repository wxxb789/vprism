"""
FastAPI 应用工厂和配置
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware

from vprism.core.client import VPrismClient
from vprism.core.config import ConfigManager
from vprism.core.exceptions import VPrismError
from vprism.web.models import ErrorResponse
from vprism.web.routes import data_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时初始化
    config_manager = ConfigManager()
    config = config_manager.get_config()
    client = VPrismClient()
    
    # 存储到应用状态
    app.state.vprism_client = client
    app.state.config = config
    
    # 启动客户端（如果支持）
    if hasattr(client, 'startup'):
        await client.startup()
    
    yield
    
    # 关闭时清理（如果支持）
    if hasattr(client, 'shutdown'):
        await client.shutdown()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="vprism - 下一代个人金融数据平台",
        description="通过现代架构和工具重新定义金融数据访问，解决akshare等传统金融数据库的核心问题",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    # 添加中间件
    _setup_middleware(app)
    
    # 注册路由
    _setup_routes(app)
    
    # 注册异常处理器
    _setup_exception_handlers(app)
    
    return app


def _setup_middleware(app: FastAPI) -> None:
    """配置中间件"""
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该配置具体域名
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Gzip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)


def _setup_routes(app: FastAPI) -> None:
    """注册路由"""
    app.include_router(data_router, prefix="/api/v1/data", tags=["data"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])


def _setup_exception_handlers(app: FastAPI) -> None:
    """配置异常处理器"""
    
    @app.exception_handler(VPrismError)
    async def vprism_exception_handler(request: Request, exc: VPrismError) -> JSONResponse:
        """处理 vprism 自定义异常"""
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=exc.__class__.__name__,
                message=str(exc),
                details={
                    "error_code": getattr(exc, 'error_code', 'UNKNOWN'),
                    "context": getattr(exc, 'context', {})
                },
                request_id=str(uuid.uuid4())
            ).dict()
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """处理 HTTP 异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error="HTTPException",
                message=exc.detail,
                details={"status_code": exc.status_code},
                request_id=str(uuid.uuid4())
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获的异常"""
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="InternalServerError",
                message="服务器内部错误",
                details={"type": type(exc).__name__},
                request_id=str(uuid.uuid4())
            ).dict()
        )


# 创建全局应用实例
app = create_app()