# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/4/28 18:07
"""
from backend.applications.knowledge_base.models.knowledge_base_model import (
    KnowledgeBase,
    Document,
    DocumentChunk,
)

__all__ = ["KnowledgeBase", "Document", "DocumentChunk"]
