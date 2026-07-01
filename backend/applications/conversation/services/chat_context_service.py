# -*- coding: utf-8
"""聊天上下文增强：M1 滚动摘要 + M2 用户记忆 → system prompt 片段。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.applications.base.rag.llm import OpenAICompatibleLLM, estimate_message_tokens, trim_chat_history
from backend.applications.conversation.models.conversation_model import Conversation, Message
from backend.applications.conversation.services.user_memory_crud import list_active_memories
from backend.applications.model_config.services.llm_connection import resolve_llm_connection
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.configure.rag_config import (
    CONVERSATION_SUMMARY_MERGE_SYSTEM_PROMPT,
    USER_MEMORY_VS_RAG_BOUNDARY_NOTE,
)


async def build_memory_system_section(
        conversation: Optional[Conversation] = None,
        user: Optional[User] = None,
) -> str:
    """组装 ## 对话摘要 / ## 用户相关信息；无内容时返回空串。"""
    parts: list[str] = []

    if conversation and (conversation.summary or "").strip():
        parts.append(f"## 对话摘要\n\n{conversation.summary.strip()}")

    if user and PROJECT_CONFIG.USER_MEMORY_ENABLED:
        memories = await list_active_memories(user.id)
        if memories:
            lines = []
            for index, item in enumerate(memories, start=1):
                prefix = f"[{item.memory_key}] " if item.memory_key else ""
                lines.append(f"{index}. {prefix}{item.content}")
            parts.append("## 用户相关信息\n\n" + "\n".join(lines))

    if parts:
        parts.insert(0, USER_MEMORY_VS_RAG_BOUNDARY_NOTE)

    return "\n\n".join(parts)


def split_messages_for_summary(
        messages: List[Message],
        *,
        max_history_rounds: int,
        max_history_tokens: int,
        covered_until_message_id: Optional[int],
) -> Tuple[List[Message], List[Message]]:
    """待摘要区：(covered_until 之后) ～ (M0 保留区第一条之前)。"""
    if not messages:
        return [], []

    history = [{"role": m.role.value, "content": m.content or ""} for m in messages]
    trimmed = trim_chat_history(history, max_history_rounds, max_history_tokens)
    if not trimmed:
        return [], []

    retained = messages[len(history) - len(trimmed):]
    cutoff = covered_until_message_id or 0
    pending = [m for m in messages if cutoff < m.id < retained[0].id]
    return pending, retained


def should_trigger_rolling_summary(
        conversation: Conversation,
        messages: List[Message],
        pending: List[Message],
) -> bool:
    if not PROJECT_CONFIG.SUMMARY_ENABLED or not pending:
        return False

    covered_id = conversation.summary_covered_until_message_id
    has_prior_summary = covered_id is not None

    if len(messages) > PROJECT_CONFIG.SUMMARY_TRIGGER_MESSAGES and not has_prior_summary:
        return True

    if has_prior_summary and len(pending) >= PROJECT_CONFIG.SUMMARY_RETRIGGER_GAP_MESSAGES:
        return True

    unsummarized_tokens = sum(
        estimate_message_tokens(m.content or "")
        for m in messages
        if m.id > (covered_id or 0)
    )
    return unsummarized_tokens > PROJECT_CONFIG.SUMMARY_TRIGGER_HISTORY_TOKENS


async def run_conversation_summary(conversation_id: str) -> None:
    """检查并执行滚动摘要；失败仅打日志，不抛出。"""
    try:
        conversation = await Conversation.filter(id=conversation_id).prefetch_related("model_config").first()
        if not conversation:
            return

        messages = await Message.filter(conversation_id=conversation_id).order_by("id").all()
        if not messages:
            return

        max_rounds = (
            conversation.model_config.max_history_rounds
            if conversation.model_config and conversation.model_config.max_history_rounds
            else 8
        )
        pending, _retained = split_messages_for_summary(
            messages,
            max_history_rounds=max_rounds,
            max_history_tokens=PROJECT_CONFIG.MAX_HISTORY_TOKENS,
            covered_until_message_id=conversation.summary_covered_until_message_id,
        )
        if not should_trigger_rolling_summary(conversation, messages, pending):
            return

        conn = resolve_llm_connection(conversation.model_config)
        llm = OpenAICompatibleLLM(
            model=conn.llm_model_name,
            api_key=conn.llm_api_key,
            base_url=conn.llm_base_url,
        )
        max_tokens = PROJECT_CONFIG.SUMMARY_MAX_TOKENS
        segment_lines = []
        for msg in pending:
            role = "用户" if msg.role.value == "user" else "助手"
            content = (msg.content or "").strip()
            if content:
                segment_lines.append(f"{role}：{content}")

        merged = llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": CONVERSATION_SUMMARY_MERGE_SYSTEM_PROMPT.format(max_chars=max_tokens * 2),
                },
                {
                    "role": "user",
                    "content": (
                        f"## 既有摘要\n{(conversation.summary or '').strip() or '（尚无摘要）'}\n\n"
                        f"## 新对话片段\n" + "\n".join(segment_lines) + "\n\n"
                        "请输出合并后的滚动摘要："
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            top_p=0.9,
            enable_thinking=False,
        )
        new_summary = (merged or "").strip()
        if not new_summary:
            return

        max_chars = max(200, max_tokens * 2)
        if len(new_summary) > max_chars:
            new_summary = new_summary[: max_chars - 3].rstrip() + "..."

        conversation.summary = new_summary
        conversation.summary_covered_until_message_id = pending[-1].id
        conversation.summary_updated_time = datetime.now(timezone.utc)
        await conversation.save(
            update_fields=["summary", "summary_covered_until_message_id", "summary_updated_time"]
        )
        LOGGER.info(
            f"[summary] updated conversation={conversation_id} "
            f"covered_until={pending[-1].id} pending={len(pending)}"
        )
    except Exception as exc:
        LOGGER.warning(f"[summary] failed conversation={conversation_id}: {exc}")
