# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py.py
@DateTime: 2025/1/12 19:46
"""
from .app_initialization import (
    build_tortoise_config,
    register_database,
    register_exceptions,
    register_middlewares,
    register_routers,
)
from .data_initialization import init_database_table

__all__ = (
    build_tortoise_config,
    register_database,
    register_exceptions,
    register_middlewares,
    register_routers,
    init_database_table
)
