"""
基础配置：服务器、数据库、Redis、Session、去重、密码
"""

from pathlib import Path
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class BaseConfig(BaseSettings):
    """服务器 / 数据库 / Redis / Session / 去重 / 密码"""

    # 服务器
    server_port: int = 8567
    server_host: str = "0.0.0.0"

    # 数据库
    db_host: str
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # Redis
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Session
    session_secret_key: str
    session_max_age: int = 2592000  # 30 天

    # 创建文章去重窗口，同一参数在此窗口内禁止重复提交
    dedup_window_seconds: int = 60

    # 密码加密：bcrypt 加密轮数（cost factor），默认 12
    bcrypt_rounds: int = 12

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
