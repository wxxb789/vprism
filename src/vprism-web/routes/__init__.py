"""
Web API 路由模块
"""

from .data_routes import router as data_router
from .health_routes import router as health_router

__all__ = ["data_router", "health_router"]
