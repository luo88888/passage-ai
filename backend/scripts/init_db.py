"""数据库初始化脚本：建库建表（幂等，可重复执行）。

用法（在 backend 目录下执行）：
    uv run python scripts/init_db.py

功能：
1. 建库（若不存在）：库名与字符集以 .env 配置为准。
2. 建表：表结构复用 backend/sql/init_db.sql 的建表 DDL，
   保证结构始终与 SQL 脚本保持一致。

说明：演示账号、模型计价等种子数据已拆分为独立脚本
`scripts/seed_data.py`，需在初始化后手动执行（见该脚本文档）。

所有操作均幂等：重复执行不会产生重复表。
"""

import sys
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

# 无论从哪个目录运行，都先把 backend 加入模块搜索路径，保证可导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402

INIT_SQL_PATH = BACKEND_DIR / "sql" / "init_db.sql"


def _create_database() -> None:
    """建库（若不存在），字符集与 init_db.sql 保持一致。"""
    root_url = (
        f"mysql+pymysql://{quote_plus(settings.db_user)}:{quote_plus(settings.db_password)}"
        f"@{settings.db_host}:{settings.db_port}/?charset=utf8mb4"
    )
    root_engine = create_engine(root_url, pool_pre_ping=True)
    try:
        with root_engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        print(f"[OK] 数据库 {settings.db_name} 已就绪")
    finally:
        root_engine.dispose()


def _extract_ddl() -> list[str]:
    """从 init_db.sql 提取建表 DDL。

    跳过文件头注释与 CREATE DATABASE / USE（库名以 .env 配置为准），
    仅保留 CREATE TABLE 语句。
    """
    sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    statements: list[str] = []
    for raw in sql.split(";"):
        # 去掉语句前导注释行（各表节标题）
        body = "\n".join(ln for ln in raw.splitlines() if not ln.strip().startswith("--"))
        stmt = body.strip()
        if not stmt:
            continue
        if stmt.upper().startswith("CREATE TABLE"):
            statements.append(stmt)
    return statements


def _create_tables() -> None:
    """执行建表 DDL（全部 CREATE ... IF NOT EXISTS，幂等）。"""
    ddl = _extract_ddl()
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    print(f"[OK] 建表完成，共执行 {len(ddl)} 条 DDL（表均 IF NOT EXISTS，幂等）")


def main() -> None:
    print("=" * 60)
    print("AI 文章创作平台 · 数据库初始化（建库建表）")
    print(f"数据库：{settings.db_user}@{settings.db_host}:{settings.db_port}/{settings.db_name}")
    print("=" * 60)

    _create_database()
    _create_tables()
    print("=" * 60)
    print("初始化完成（全部幂等，可重复执行）")
    print("提示：种子数据（演示账号/模型计价）请手动执行 scripts/seed_data.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
    engine.dispose()
