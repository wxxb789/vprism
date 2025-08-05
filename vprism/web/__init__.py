"""
Web API 模块 - FastAPI 网络服务实现
"""

from vprism.web.app import create_app
from vprism.web.models import APIResponse, ErrorResponse
from vprism.web.routes import data_router, health_router

__all__ = ["create_app", "data_router", "health_router", "APIResponse", "ErrorResponse"]
