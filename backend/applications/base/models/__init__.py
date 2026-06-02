"""Tortoise ORM 模型聚合（供 Aerich 发现）"""

from backend.applications.user.models.user import User
from backend.applications.knowledge_base.models.knowledge_base import (
    KnowledgeBase,
    Document,
    DocumentChunk,
)
from backend.applications.model_config.models.model_config import ModelConfig
from backend.applications.conversation.models.conversation import Conversation, Message

__all__ = [
    "User",
    "KnowledgeBase",
    "Document",
    "DocumentChunk",
    "ModelConfig",
    "Conversation",
    "Message",
]
