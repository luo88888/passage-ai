"""路由模块"""

from app.routers.health import health_router
from app.routers.user import router as user_router

__all__ = ["health_router", "user_router"]
