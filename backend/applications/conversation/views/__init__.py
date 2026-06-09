# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/4/28 18:07
"""
from backend.applications.conversation.views.chat_view import router as chat_router
from backend.applications.conversation.views.history_view import router as history_router

__all__ = ["chat_router", "history_router"]
