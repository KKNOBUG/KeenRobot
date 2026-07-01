# -*- coding: utf-8 -*-
"""评测 CLI 数据库会话。"""
from contextlib import asynccontextmanager

from tortoise import Tortoise

from backend.celery_scheduler.celery_base import init_tortoise_orm


@asynccontextmanager
async def tortoise_session():
    await init_tortoise_orm()
    try:
        yield
    finally:
        await Tortoise.close_connections()
