# -*- coding: utf-8 -*-
"""检索 query 轻量增强（P1-1）：指代/省略问法补全，规则优先、无 LLM。"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from backend.configure import PROJECT_CONFIG

# 省略/指代追问常见开头或句式
_ELLIPTICAL_PATTERN = re.compile(
    r"^(那|这|这个|那个|它|它们|还有|继续|刚才|上面|前面|同样|也|再|然后呢|接下来)",
    re.IGNORECASE,
)
_SHORT_QUESTION_MAX_LEN = 18


def _last_user_message(chat_history: List[Dict[str, str]]) -> str:
    for msg in reversed(chat_history):
        if (msg.get("role") or "").strip() == "user":
            content = (msg.get("content") or "").strip()
            if content:
                return content
    return ""


def is_elliptical_followup(question: str) -> bool:
    """当前问是否像多轮追问/省略主语。"""
    text = (question or "").strip()
    if not text:
        return False
    if _ELLIPTICAL_PATTERN.search(text):
        return True
    if len(text) <= _SHORT_QUESTION_MAX_LEN and text.endswith(("呢", "吗", "?", "？")):
        return True
    return len(text) <= 8


def enhance_retrieval_query(
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    为向量检索生成补全后的 compact query。
    仅在有历史且当前问为省略/指代时使用「上一轮用户问 + 当前问」。
    """
    current = (question or "").strip()
    if not current or not chat_history:
        return current

    if not PROJECT_CONFIG.RETRIEVAL_QUERY_ENHANCE_ENABLED:
        return current

    if not is_elliptical_followup(current):
        return current

    prior_user = _last_user_message(chat_history)
    if not prior_user or prior_user == current:
        return current

    return f"{prior_user}；{current}"


def build_retrieval_query(
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        *,
        context_turns: Optional[int] = None,
) -> str:
    """
    检索专用 query：省略追问用 compact 补全；否则 M0.2 拼接最近 N 轮。
    """
    from backend.applications.base.rag.retriever import build_query

    turns = context_turns if context_turns is not None else PROJECT_CONFIG.RETRIEVAL_QUERY_CONTEXT_TURNS
    compact = enhance_retrieval_query(question, chat_history)
    current = (question or "").strip()

    if compact != current:
        return compact

    return build_query(question, chat_history, context_turns=turns)


def build_empty_retry_query(
        question: str,
        chat_history: Optional[List[Dict[str, str]]],
        first_query: str,
) -> Optional[str]:
    """
    空召回时生成 alternate query（最多使用第一个有效变体）。
    策略：当前问 only → 全量多轮 query → compact 补全。
    """
    if not PROJECT_CONFIG.RETRIEVAL_EMPTY_RETRY_ENABLED:
        return None

    current = (question or "").strip()
    first = (first_query or "").strip()
    if not current or current == first:
        # first 已是 bare question 时，尝试多轮 query
        if chat_history:
            from backend.applications.base.rag.retriever import build_query

            full = build_query(
                current,
                chat_history,
                context_turns=PROJECT_CONFIG.RETRIEVAL_QUERY_CONTEXT_TURNS,
            )
            if full != first:
                return full
        return None

    # first 含对话或 compact 时，优先 bare question
    return current


def build_fusion_queries(
        question: str,
        chat_history: Optional[List[Dict[str, str]]],
        primary_query: str,
) -> List[str]:
    """
    多 query 向量融合（P2-2）：primary / bare / 多轮 / compact，去重后最多 N 条。
    关闭 RETRIEVAL_MULTI_QUERY_FUSION_ENABLED 时仅返回 primary。
    """
    primary = (primary_query or "").strip()
    if not PROJECT_CONFIG.RETRIEVAL_MULTI_QUERY_FUSION_ENABLED:
        return [primary] if primary else []

    max_queries = max(2, min(3, int(PROJECT_CONFIG.RETRIEVAL_MULTI_QUERY_MAX or 3)))
    queries: List[str] = []

    def add(text: str) -> None:
        q = (text or "").strip()
        if q and q not in queries:
            queries.append(q)

    add(primary)
    add(question)
    if chat_history:
        from backend.applications.base.rag.retriever import build_query

        add(
            build_query(
                question,
                chat_history,
                context_turns=PROJECT_CONFIG.RETRIEVAL_QUERY_CONTEXT_TURNS,
            )
        )
        add(enhance_retrieval_query(question, chat_history))

    return queries[:max_queries]
