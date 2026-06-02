"""Tortoise ORM 初始化"""

from tortoise import Tortoise

from backend.configure.config import TORTOISE_ORM


async def init_db() -> None:
    # FastAPI lifespan 运行在独立 task 中，需启用 global fallback 供请求 handler 访问连接
    await Tortoise.init(config=TORTOISE_ORM, _enable_global_fallback=True)


async def close_db() -> None:
    await Tortoise.close_connections()
