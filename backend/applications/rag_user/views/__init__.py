# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/4/28 18:07
"""
from backend.applications.rag_user.views.auth_view import router as auth_router

__all__ = ["auth_router"]
