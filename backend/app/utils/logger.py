"""
日志工具
统一管理项目中的日志记录，支持控制台输出与文件自动轮换。
用法:
    from app.utils.logger import logger
    logger.info("...")
    logger.error("...")
"""

import logging
from logging.handlers import RotatingFileHandler

from app.utils.path_tool import get_abs_path


# 日志文件存放目录：backend/logs/
LOG_DIR = get_abs_path("logs")
# 目录不存在则自动创建（parents=True 允许逐级创建，exist_ok=True 避免已存在时报错）
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志文件路径
LOG_FILE = LOG_DIR / "app.log"

# 日志格式：时间 | 级别 | 文件名:行号 | 消息
LOG_FMT = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

# 单个日志文件最大字节数（10MB）与保留的历史文件数
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 7


def _make_console_handler() -> logging.Handler:
    """控制台 handler：输出到 stdout，级别 INFO"""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FMT, datefmt=DATE_FMT))
    return console_handler


def _make_file_handler() -> logging.Handler:
    """文件 handler：按大小自动轮换，debug 级别全量写入文件"""
    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FMT, datefmt=DATE_FMT))
    return file_handler


def get_logger(name: str = "app") -> logging.Logger:
    """
    获取一个已配置好的 logger。
    - 同时输出到控制台和文件
    - 文件按大小自动轮换：单个文件最大 10MB，最多保留 7 个历史文件
    - 防止重复添加 handler（多次调用不会重复输出）

    Args:
        name: logger 名称，默认 "app"

    Returns:
        logging.Logger: 已配置好的 logger 实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler（多次 import / 调用时）
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    logger.addHandler(_make_console_handler())
    logger.addHandler(_make_file_handler())

    # 防止日志向 root logger 传递导致重复输出
    logger.propagate = False

    return logger


# 全局默认 logger，供各模块直接 import 使用
logger = get_logger("app")


def _configure_uvicorn_loggers() -> None:
    """
    将 uvicorn / uvicorn.error / uvicorn.access 的日志挂到同一套 handler 上。
    这样 uvicorn 的启动日志和 HTTP 访问日志也会被轮换并写入文件。
    """
    uvicorn_formatter = logging.Formatter(LOG_FMT, datefmt=DATE_FMT)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        # 清理 uvicorn 自带的 handler，改用项目的控制台 + 文件 handler
        uv_logger.handlers = []
        uv_logger.setLevel(logging.INFO)
        uv_logger.propagate = False

        console = _make_console_handler()
        file = _make_file_handler()
        console.setFormatter(uvicorn_formatter)
        file.setFormatter(uvicorn_formatter)
        uv_logger.addHandler(console)
        uv_logger.addHandler(file)


# 模块导入时即配置好 uvicorn 的日志
_configure_uvicorn_loggers()


if __name__ == "__main__":
    logger.debug("这是一条 DEBUG 日志（仅写入文件）")
    logger.info("这是一条 INFO 日志（写入文件并输出到控制台）")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")