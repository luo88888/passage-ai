"""
FastAPI 主程序入口
启动方式: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8567
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import database
from app.routers import (
    user_router,
    health_router,
    article_router,
    payment_router,
    webhook_router,
    statistics_router
)
from app.exceptions import BusinessException, ErrorCode
from app.utils.session import init_redis, close_redis
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""

    # 启动时执行
    logger.info("应用启动中...")
    await database.connect()
    logger.info("数据库连接成功")
    await init_redis()
    logger.info("Redis 初始化成功")
    logger.info(f"数据库连接成功：{settings.database_url}")
    logger.info(f"Redis 连接成功：{settings.redis_url}")

    yield   # 分隔启动和关闭逻辑

    # 关闭时执行
    await database.disconnect()
    await close_redis()
    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="AI 爆款文章创作器",
    description="基于多智能体编排的 AI 文章生成平台",
    version="0.0.1",
    lifespan=lifespan
)


# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",

        "http://localhost:5174",
        "http://127.0.0.1:5174",
        
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ], # 前端开发服务器地址
    allow_credentials=True, # 允许携带 Cookie 或 Session 凭证
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常处理"""
    return JSONResponse(
        status_code=200,
        content={
            "code": exc.error_code.code,
            "data": None,
            "message": exc.message
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"未处理的异常：{exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content={
            "code": ErrorCode.SYSTEM_ERROR.code,
            "data": None,
            # HACK: 不太安全，可能暴露技术细节
            "message": f"系统内部异常：{str(exc)}"
        }
    )


# 注册路由
app.include_router(health_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(article_router, prefix="/api")
app.include_router(payment_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(statistics_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True
    )