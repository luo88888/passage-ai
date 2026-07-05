"""LangGraph SQLite Checkpointer 单例管理

使用 langgraph-checkpoint-sqlite 的 AsyncSqliteSaver 持久化图状态。
生命周期由 app/main.py 的 lifespan 托管：startup 调 init_checkpointer，shutdown 调 close_checkpointer。

SQLite 文件路径：backend/data/checkpoints.sqlite（backend/data 见 .gitignore）。
"""
from __future__ import annotations

import os
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from app.utils.logger import logger

if TYPE_CHECKING:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 默认相对 backend 工作目录（uv run uvicorn 在 backend/ 下启动）
_DEFAULT_PATH = os.path.join("data", "checkpoints.sqlite")

_stack: AsyncExitStack | None = None
_checkpointer: "AsyncSqliteSaver | None" = None


async def init_checkpointer(path: str = _DEFAULT_PATH) -> None:
    """startup 调：建目录 + 进入 AsyncSqliteSaver.from_conn_string 上下文 + setup()"""
    global _stack, _checkpointer
    if _checkpointer is not None:
        logger.warning("checkpointer 已初始化，跳过重复 init")
        return

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    _stack = AsyncExitStack()
    _checkpointer = await _stack.enter_async_context(
        AsyncSqliteSaver.from_conn_string(path)
    )
    await _checkpointer.setup()
    logger.info("SQLite checkpointer 初始化成功, path=%s", path)


async def close_checkpointer() -> None:
    """shutdown 调：退出上下文，释放 aiosqlite 连接"""
    global _stack, _checkpointer
    if _stack is not None:
        await _stack.aclose()
        logger.info("SQLite checkpointer 已关闭")
    _stack = None
    _checkpointer = None


def get_checkpointer() -> "AsyncSqliteSaver":
    """获取已初始化的 checkpointer 单例。

    使用前需确保 lifespan 已调用 init_checkpointer。
    """
    if _checkpointer is None:
        raise RuntimeError("checkpointer 未初始化，请在应用启动时调用 init_checkpointer()")
    return _checkpointer