# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_data
@DateTime: 2026/6/7 12:39

保留兼容入口；实际初始化逻辑在 core.initializations.data_initialization。
"""
from backend.core.initializations.data_initialization import init_database_users_with_roles as init_database_user

__all__ = ["init_database_user"]
