"""种子数据脚本：演示账号 / 模型计价（幂等，可重复执行，需手动运行）。

注意：
1. 已存在的用户数据会被刷新
2. 已存在的模型定价将跳过

用法（在 backend 目录下执行，需先执行 scripts/init_db.py 完成建库建表）：
    uv run python scripts/seed_data.py

写入内容：
1. 模型计价 model_pricing（INSERT IGNORE，唯一键 uk_model）
2. 演示账号 admin / user / test：密码 12345678 由 bcrypt 加密（先 SHA-256
   预哈希，自带随机盐），头像默认使用
   backend/static/default_avatar/0ca3d6k8f81f9dsf905949eckad953ar.png

所有操作均幂等：重复执行不会产生重复数据。
"""

import sys
from pathlib import Path

from sqlalchemy import text

# 无论从哪个目录运行，都先把 backend 加入模块搜索路径，保证可导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.utils.password import encrypt_password  # noqa: E402

# 默认头像（backend/static 下的相对路径，经 /static 挂载访问）
DEFAULT_AVATAR = "default_avatar/0ca3d6k8f81f9dsf905949eckad953ar.png"

# 演示账号：(账号, 昵称, 简介, 角色, 配额, 密码)
DEMO_USERS = [
    ("admin", "管理员", "系统管理员", "admin", 5, "12345678"),
    ("user", "普通用户", "我是一个普通用户", "user", 5, "12345678"),
    ("test", "测试账号", "这是一个测试账号", "user", 5, "12345678"),
]

# 模型计价种子：(category, provider, model, agentName, inputPricePer1k, outputPricePer1k, pricePerImage, enabled)
MODEL_PRICING_SEEDS = [
    ("LLM", "Xiaomi", "mimo-v2.5-pro", "", 1.0000, 2.0000, 0, 1),
    ("LLM", "Xiaomi", "mimo-v2.5", "", 0.3000, 0.6000, 0, 1),
    ("LLM", "DeepSeek", "deepseek-v4-flash", "", 0.3000, 0.6000, 0, 1),
    ("LLM", "*", "*", "", 1.0000, 2.0000, 0, 1),
    ("IMAGE", "Zhipu", "cogview-3-flash", "", 0, 0, 0, 1),
    ("IMAGE", "NanoBanana", "gemini-2.5-flash-image", "", 0, 0, 2.00, 1),
]


def _check_tables() -> None:
    """前置校验：确认核心表已存在（缺失时提示先执行 init_db.py）。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema"
            ),
            {"schema": settings.db_name},
        ).fetchall()
    tables = {row[0] for row in rows}
    required = ("user", "model_pricing")
    missing = [t for t in required if t not in tables]
    if missing:
        raise SystemExit(
            "缺少表：" + "、".join(missing)
            + "。请先执行 scripts/init_db.py 完成建库建表，再手动运行本脚本。"
        )


def _seed_users(conn) -> None:
    """幂等写入演示账号（账号唯一，重复执行仅刷新字段）。"""
    avatar_url = f"{settings.static_base_url.rstrip('/')}/static/{DEFAULT_AVATAR}"
    avatar_file = BACKEND_DIR / "static" / DEFAULT_AVATAR
    if not avatar_file.exists():
        print(f"[WARN] 默认头像文件不存在：{avatar_file}")
        print("       仍将写入头像 URL，请确保部署时包含该文件。")


    sql = text(
        "INSERT INTO user "
        "(userAccount, userPassword, userName, userAvatar, userProfile, userRole, quota) "
        "VALUES (:account, :password, :name, :avatar, :profile, :role, :quota) AS new "
        "ON DUPLICATE KEY UPDATE "
        "userPassword = new.userPassword, "
        "userName = new.userName, "
        "userAvatar = new.userAvatar, "
        "userProfile = new.userProfile, "
        "userRole = new.userRole, "
        "quota = new.quota"
    )
    for account, name, profile, role, quota, password in DEMO_USERS:
        encrypted = encrypt_password(password)
        conn.execute(
            sql,
            {
                "account": account,
                "password": encrypted,
                "name": name,
                "avatar": avatar_url,
                "profile": profile,
                "role": role,
                "quota": quota,
            },
        )
        print(f"[OK] 用户 {account} 已写入（幂等，重复执行仅刷新字段）")


def _seed_model_pricing(conn) -> None:
    """幂等写入模型计价种子（INSERT IGNORE，唯一键 category+provider+model+agentName）。"""
    sql = text(
        "INSERT IGNORE INTO model_pricing "
        "(category, provider, model, agentName, inputPricePer1k, outputPricePer1k, pricePerImage, enabled) "
        "VALUES (:category, :provider, :model, :agentName, :inputPricePer1k, :outputPricePer1k, "
        ":pricePerImage, :enabled)"
    )
    for row in MODEL_PRICING_SEEDS:
        conn.execute(
            sql,
            {
                "category": row[0],
                "provider": row[1],
                "model": row[2],
                "agentName": row[3],
                "inputPricePer1k": row[4],
                "outputPricePer1k": row[5],
                "pricePerImage": row[6],
                "enabled": row[7],
            },
        )
    print(f"[OK] 模型计价种子已写入 {len(MODEL_PRICING_SEEDS)} 条（INSERT IGNORE，幂等）")


def main() -> None:
    print("=" * 60)
    print("AI 文章创作平台 · 种子数据（需手动执行）")
    print(f"数据库：{settings.db_user}@{settings.db_host}:{settings.db_port}/{settings.db_name}")
    print("=" * 60)

    _check_tables()

    answer = input("注意：会刷新所有演示用户的数据，已存在的模型定价将跳过，输入 yes 继续: ")
    if answer == "yes":
        with engine.begin() as conn:
            _seed_users(conn)
            _seed_model_pricing(conn)
        print("=" * 60)
        print("种子数据写入完成（全部幂等，可重复执行）")
        print("=" * 60)
    else:
        print("流程已终止，未修改任何数据")

if __name__ == "__main__":
    main()
    engine.dispose()
