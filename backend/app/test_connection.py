"""
测试 .env 配置能否真正连上 MySQL 和 Redis
注意：这里会真正发起连接，不是只创建客户端对象。
"""

import asyncio

from app.config import settings
from app.utils.session import init_redis, close_redis, get_session, set_session
from app.database import database


async def test_mysql():
    """真正连接 MySQL 并执行一条查询"""
    print("\n[1/2] 测试 MySQL 连接 ...")
    try:
        await database.connect()
        # 执行一条真实查询，验证连接确实可用
        rows = await database.fetch_all("SELECT 1 AS ok, NOW() AS server_time, DATABASE() AS db, USER() AS user")
        row = rows[0]
        print(f"  ✅ MySQL 连接成功")
        print(f"     查询结果: ok={row['ok']}, db={row['db']}, user={row['user']}, time={row['server_time']}")
    except Exception as e:
        print(f"  ❌ MySQL 连接失败: {type(e).__name__}: {e}")
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass


async def test_redis():
    """真正连接 Redis 并执行一次 set/get"""
    print("\n[2/2] 测试 Redis 连接 ...")
    try:
        await init_redis()
        # 真正发起一次 SET + GET，验证连接确实可用
        test_id = "conn-test-123456"
        await set_session(test_id, {"ping": "pong"}, expire=10)
        data = await get_session(test_id)
        if data and data.get("ping") == "pong":
            print(f"  ✅ Redis 连接成功")
            print(f"     写入并读回测试数据: {data}")
        else:
            print(f"  ❌ Redis 连接异常: 写入后读回数据不匹配 -> {data}")
    except Exception as e:
        print(f"  ❌ Redis 连接失败: {type(e).__name__}: {e}")
    finally:
        await close_redis()


async def main():
    print("=" * 50)
    print("使用 .env 中的配置进行真实连接测试")
    print("=" * 50)
    print(f"MySQL URL: {settings.database_url}")
    print(f"Redis URL: {settings.redis_url}")

    await test_mysql()
    await test_redis()

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
