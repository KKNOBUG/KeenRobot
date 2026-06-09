# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : conversation_model.py
@DateTime: 2025/4/28 18:07
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    MaintainMixin,
    TimestampMixin,
    StateModel,
    unique_identify
)


class Conversation(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """对话会话"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="conversations",
        on_delete=fields.CASCADE
    )
    title = fields.CharField(default="新对话", max_length=255)
    knowledge_ids = fields.TextField(null=True, description="知识关联ID列表")
    model_config = fields.ForeignKeyField(
        "models.ModelConfig",
        related_name="conversations",
        null=True,
        on_delete=fields.SET_NULL,
    )
    messages: fields.ReverseRelation["Message"]

    class Meta:
        table = "keenrobot_conversations"


class Message(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """聊天消息"""

    id = fields.IntField(pk=True)
    conversation = fields.ForeignKeyField(
        "models.Conversation",
        related_name="messages",
        on_delete=fields.CASCADE
    )
    role = fields.CharField(max_length=20)
    content = fields.TextField()

    class Meta:
        table = "keenrobot_messages"
        ordering = ["created_time"]
