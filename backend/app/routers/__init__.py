"""路由模块"""

from app.routers.health import health_router
from app.routers.user import router as user_router
from app.routers.article import router as article_router
from app.routers.payment import payment_router, webhook_router
from app.routers.statistics import router as statistics_router
from app.routers.points import router as points_router
from app.routers.admin_points import admin_points_router, model_pricing_router

__all__ = [
    "health_router",
    "user_router",
    "article_router",
    "payment_router",
    "webhook_router",
    "statistics_router",
    "points_router",
    "admin_points_router",
    "model_pricing_router"
]
