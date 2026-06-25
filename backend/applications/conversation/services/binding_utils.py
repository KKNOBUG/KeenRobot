# -*- coding: utf-8 -*-
"""会话绑定 ID 读取与解析结果。"""
from dataclasses import dataclass
from typing import List, Optional

from backend.applications.conversation.models.conversation_model import Conversation
from backend.applications.conversation.schemas.conversation_schema import (
    normalize_knowledge_base_ids,
    normalize_mcp_ids,
    normalize_skill_ids,
)
from backend.applications.model_config.models.model_config_model import ModelConfig


def kb_ids_from_conversation(conversation: Conversation) -> List[str]:
    ids = normalize_knowledge_base_ids(conversation.knowledge_base_ids)
    return ids if ids is not None else []


def skill_ids_from_conversation(conversation: Conversation) -> List[str]:
    ids = normalize_skill_ids(conversation.skill_ids)
    return ids if ids is not None else []


def mcp_ids_from_conversation(conversation: Conversation) -> List[str]:
    ids = normalize_mcp_ids(conversation.mcp_ids)
    return ids if ids is not None else []


@dataclass
class ResolvedConversationBindings:
    knowledge_base_ids: List[str]
    skill_ids: List[str]
    mcp_ids: List[str]
    model_config: Optional[ModelConfig]
    model_config_id: Optional[str]
    enable_thinking: bool
    chat_skill_ids: List[str]
