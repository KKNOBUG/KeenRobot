# -*- coding: utf-8
"""M2 用户显式记忆：读写与校验。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from backend.applications.conversation.models.user_memory_model import UserMemory
from backend.applications.conversation.services.explicit_memory_parser import (
    infer_memory_key,
    is_sensitive_memory_content,
    normalize_memory_key,
    parse_explicit_memory_request,
)
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException


async def list_active_memories(user_id: int, *, limit: Optional[int] = None) -> List[UserMemory]:
    if not PROJECT_CONFIG.USER_MEMORY_ENABLED:
        return []
    cap = limit or PROJECT_CONFIG.USER_MEMORY_MAX_ITEMS
    now = datetime.now()
    rows = await UserMemory.filter(user_id=user_id, state=0).order_by("-updated_time").limit(cap * 2)
    active: List[UserMemory] = []
    for row in rows:
        if row.expires_at and row.expires_at < now:
            continue
        active.append(row)
        if len(active) >= cap:
            break
    return active


async def create_explicit_memory(
        user: User,
        content: str,
        *,
        memory_key: Optional[str] = None,
) -> UserMemory:
    if not PROJECT_CONFIG.USER_MEMORY_ENABLED:
        raise ParameterException(message="用户记忆功能未启用")

    max_len = PROJECT_CONFIG.USER_MEMORY_MAX_CONTENT_CHARS
    body = (content or "").strip()
    if len(body) > max_len:
        body = body[: max_len - 3].rstrip() + "..."
    if not body:
        raise ParameterException(message="记忆内容不能为空")
    if is_sensitive_memory_content(body):
        raise ParameterException(message="该内容涉及敏感信息，无法保存为记忆")

    key = normalize_memory_key(memory_key or infer_memory_key(body))
    record = await UserMemory.create(
        user=user,
        content=body,
        memory_key=key,
        source="explicit",
    )
    LOGGER.info(f"[memory] explicit saved user={user.id} key={key or '-'}")
    return record


async def try_save_explicit_memory_from_question(user: User, question: str) -> Optional[UserMemory]:
    parsed = parse_explicit_memory_request(question)
    if not parsed:
        return None
    try:
        return await create_explicit_memory(user, parsed)
    except ParameterException as exc:
        LOGGER.info(f"[memory] explicit write skipped user={user.id}: {exc.message}")
        return None


async def soft_delete_memory(user_id: int, memory_id: str) -> bool:
    record = await UserMemory.get_or_none(id=memory_id, user_id=user_id, state=0)
    if not record:
        return False
    record.state = 1
    await record.save(update_fields=["state", "updated_time"])
    return True
