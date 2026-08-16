"""
数据库连接管理
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database

from app.config import settings


# SQLAlchemy 同步引擎（用于模型定义等操作）
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True, # 在从连接池获取连接前，先发送一个轻量级的 ping 命令，防止使用已断开的死连接（非常实用的生产配置）
    pool_recycle=3600,  # 每隔 3600 秒回收并重建连接，防止数据库服务端主动断开空闲连接（如 MySQL 默认的 8 小时超时）。
    echo=False          # 关闭 SQL 日志回显
)

# 会话工厂
# autoflush=False: 不自动将内存中的更改刷新到数据库
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 模型基类
Base = declarative_base()

# databases 异步数据库（用于 FastApi 异步查询）
database = Database(settings.database_url.replace("+pymysql", ""))


async def get_db():
    """
    获取数据库连接（依赖注入）
    """
    yield database