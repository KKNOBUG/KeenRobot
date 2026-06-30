# -*- coding: utf-8 -*-
"""M2 用户显式长期记忆（仅「记住…」写入）。"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    StateModel,
    TimestampMixin,
    unique_identify,
)


class UserMemory(ScaffoldModel, StateModel, TimestampMixin):
    id = fields.CharField(
        default=unique_identify,
        max_length=64,
        primary_key=True,
        description="记忆 ID",
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="user_memories",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    memory_key = fields.CharField(
        max_length=64,
        null=True,
        description="可选分类（department / preference 等）",
    )
    content = fields.CharField(max_length=255, description="记忆正文（≤200 字）")
    source = fields.CharField(max_length=32, default="explicit", description="来源，固定 explicit")
    expires_at = fields.DatetimeField(null=True, description="可选过期时间")

    class Meta:
        table = "keenrobot_user_memories"
        ordering = ["-updated_time"]
