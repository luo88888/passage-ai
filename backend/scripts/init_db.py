"""数据库初始化脚本：建库建表 + 种子数据（幂等，可重复执行）。

用法（在 backend 目录下执行）：
    uv run python scripts/init_db.py

功能：
1. 建库（若不存在）+ 建表：表结构复用 backend/sql/init_db.sql 的建表 DDL，
   保证结构始终与 SQL 脚本保持一致。
2. 种子数据（由本脚本幂等写入）：
   - 模型计价 model_pricing（INSERT IGNORE，唯一键 uk_model）
   - 演示账号 admin / user / test：密码 12345678 使用 .env 中 PASSWORD_SALT 盐值加密
     （MD5(password + salt)），头像默认使用
     backend/static/default_avatar/0ca3d6k8f81f9dsf905949eckad953ar.png
   - 积分账户 user_points + 历史配额折算流水（1 quota = 100 积分，类型 ADMIN_ADJUST），
     并同步 user.points 冗余展示字段

所有操作均幂等：重复执行不会产生重复数据。
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# 无论从哪个目录运行，都先把 backend 加入模块搜索路径，保证可导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.constants.points import PointsConstant  # noqa: E402
from app.database import engine  # noqa: E402
from app.utils.password import encrypt_password  # noqa: E402

INIT_SQL_PATH = BACKEND_DIR / "sql" / "init_db.sql"

# 默认头像（backend/static 下的相对路径，经 /static 挂载访问）
DEFAULT_AVATAR = "default_avatar/0ca3d6k8f81f9dsf905949eckad953ar.png"
DEFAULT_PASSWORD = "12345678"

# 演示账号：(账号, 昵称, 简介, 角色, 配额)
DEMO_USERS = [
    ("admin", "管理员", "系统管理员", "admin", 5),
    ("user", "普通用户", "我是一个普通用户", "user", 5),
    ("test", "测试账号", "这是一个测试账号", "user", 5),
]

# 模型计价种子：(category, provider, model, agentName, inputPricePer1k, outputPricePer1k, pricePerImage, enabled)
# 与 backend/sql/add_points_system.sql / init_db.sql 的种子一致（100 积分 = 1 元）
MODEL_PRICING_SEEDS = [
    ("LLM", "Xiaomi", "mimo-v2.5-pro", "", 1.0000, 2.0000, 0, 1),
    ("LLM", "Xiaomi", "mimo-v2.5", "", 0.3000, 0.6000, 0, 1),
    ("LLM", "DeepSeek", "deepseek-v4-flash", "", 0.3000, 0.6000, 0, 1),
    ("LLM", "*", "*", "", 1.0000, 2.0000, 0, 1),
    ("IMAGE", "Zhipu", "cogview-3-flash", "", 0, 0, 0, 1),
    ("IMAGE", "NanoBanana", "gemini-2.5-flash-image", "", 0, 0, 2.00, 1),
]


def _create_database() -> None:
    """建库（若不存在），字符集与 init_db.sql 保持一致。"""
    root_url = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
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

    跳过 CREATE DATABASE / USE（库名以 .env 配置为准）与末尾种子数据段
    （种子数据由本脚本幂等写入，且头像/密码与 SQL 内嵌默认值不同）。
    """
    sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    sql = sql.split("-- 种子数据")[0]
    statements: list[str] = []
    for raw in sql.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        upper = stmt.upper()
        if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
            continue
        statements.append(stmt)
    return statements


def _create_tables() -> None:
    """执行建表 DDL（全部 CREATE ... IF NOT EXISTS，幂等）。"""
    ddl = _extract_ddl()
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    print(f"[OK] 建表完成，共执行 {len(ddl)} 条 DDL（表均 IF NOT EXISTS，幂等）")


def _seed_users(conn) -> None:
    """幂等写入演示账号（账号唯一，重复执行仅刷新字段）。"""
    avatar_url = f"{settings.static_base_url.rstrip('/')}/static/{DEFAULT_AVATAR}"
    avatar_file = BACKEND_DIR / "static" / DEFAULT_AVATAR
    if not avatar_file.exists():
        print(f"[WARN] 默认头像文件不存在：{avatar_file}")
        print("       仍将写入头像 URL，请确保部署时包含该文件。")

    encrypted = encrypt_password(DEFAULT_PASSWORD)
    print(f"[INFO] 密码 {DEFAULT_PASSWORD} + 盐值 {settings.password_salt} 加密 => {encrypted}")

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
    for account, name, profile, role, quota in DEMO_USERS:
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


def _seed_points(conn) -> None:
    """积分账户 + 历史配额折算流水（1 quota = 100 积分），并同步 user.points 冗余字段。

    - 积分账户：INSERT IGNORE（userId 唯一键），已存在则跳过
    - 折算流水：同一用户已存在 ADMIN_ADJUST + 「历史配额折算」描述则跳过
    - balanceAfter 取折算后账户当前余额，保证流水与账户一致
    """
    rate = PointsConstant.QUOTA_TO_POINTS_RATE
    users = conn.execute(text("SELECT id, quota FROM user WHERE isDelete = 0")).fetchall()
    for user_id, quota in users:
        points = quota * rate
        conn.execute(
            text(
                "INSERT IGNORE INTO user_points "
                "(userId, balance, totalEarned, totalConsumed, version) "
                "VALUES (:userId, :balance, :totalEarned, 0, 0)"
            ),
            {"userId": user_id, "balance": points, "totalEarned": points},
        )
        # 折算流水幂等：同用户 + ADMIN_ADJUST + 「历史配额折算」前缀存在则跳过
        existed = conn.execute(
            text(
                "SELECT COUNT(*) FROM points_transaction "
                "WHERE userId = :userId AND type = :txType AND description LIKE :descPrefix"
            ),
            {
                "userId": user_id,
                "txType": PointsConstant.TX_ADMIN_ADJUST,
                "descPrefix": "历史配额折算%",
            },
        ).scalar()
        if existed:
            continue
        if quota > 0:
            balance_after = conn.execute(
                text("SELECT balance FROM user_points WHERE userId = :userId"),
                {"userId": user_id},
            ).scalar()
            conn.execute(
                text(
                    "INSERT INTO points_transaction "
                    "(userId, taskId, type, amount, balanceAfter, description) "
                    "VALUES (:userId, NULL, :type, :amount, :balanceAfter, :description)"
                ),
                {
                    "userId": user_id,
                    "type": PointsConstant.TX_ADMIN_ADJUST,
                    "amount": points,
                    "balanceAfter": balance_after,
                    "description": f"历史配额折算（1 quota = {rate} 积分）",
                },
            )
            print(f"[OK] 用户 {user_id} 折算流水已写入：{quota} quota -> {points} 积分")
    # 同步 user.points 冗余展示字段（权威以 user_points 为准）
    conn.execute(
        text(
            "UPDATE user u JOIN user_points up ON up.userId = u.id "
            "SET u.points = up.balance WHERE u.isDelete = 0"
        )
    )
    print("[OK] 积分账户/折算流水已就绪，user.points 冗余字段已同步")


def main() -> None:
    print("=" * 60)
    print("AI 文章创作平台 · 数据库初始化")
    print(f"数据库：{settings.db_user}@{settings.db_host}:{settings.db_port}/{settings.db_name}")
    print(f"密码盐值：{settings.password_salt}")
    print("=" * 60)

    _create_database()
    _create_tables()
    with engine.begin() as conn:
        _seed_users(conn)
        _seed_model_pricing(conn)
        _seed_points(conn)
    print("=" * 60)
    print("初始化完成（全部幂等，可重复执行）")
    print("=" * 60)


if __name__ == "__main__":
    main()
    engine.dispose()
