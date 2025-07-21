"""
Web API 模块 - FastAPI 网络服务实现
"""

from .app import create_app
from .models import APIResponse, ErrorResponse
from .routes import data_router, health_router

__all__ = ["create_app", "data_router", "health_router", "APIResponse", "ErrorResponse"]
