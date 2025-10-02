"""
Web API 路由模块
"""

from vprism.web.metrics import router as metrics_router
from vprism.web.routes.data_routes import router as data_router
from vprism.web.routes.health_routes import router as health_router

__all__ = ["data_router", "health_router", "metrics_router"]
