# -*- coding: utf-8 -*-
"""统一 RAG 检索入口：向量扩召回 → 阈值过滤 → Rerank 降级 → 上下文拼装。"""

from dataclasses import dataclass
from typing import List, Dict, Optional

from backend.configure import PROJECT_CONFIG
from backend.applications.base.rag.embeddings import get_single_embedding, is_embedding_configured
from backend.applications.base.rag.chroma_store import chroma_store
from backend.applications.base.rag.reranker import apply_rerank
from backend.applications.knowledge_base.models.knowledge_base_model import DocumentChunk


def _format_source_label(result: dict) -> str:
    """格式化检索结果的来源标注"""
    filename = (result.get("filename") or "").strip()
    page_number = result.get("page_number")
    if filename and page_number:
        return f"来源: {filename} 第{page_number}页"
    if filename:
        return f"来源: {filename}"
    if page_number:
        return f"来源: 第{page_number}页"
    return ""


def _filter_embedding_model_consistency(results: List[dict]) -> List[dict]:
    """过滤与当前 Embedding 模型不一致的检索结果"""
    current_model = PROJECT_CONFIG.EMBEDDING_MODEL_NAME
    filtered = []
    for item in results:
        stored_model = (item.get("embedding_model") or "").strip()
        if stored_model and stored_model != current_model:
            print(
                f"[rag] 跳过 embedding 模型不一致的向量: "
                f"{stored_model} != {current_model}"
            )
            continue
        filtered.append(item)
    return filtered


def format_context_from_results(results: List[dict]) -> str:
    """将检索结果格式化为上下文字符串"""
    parts = []
    for i, result in enumerate(results, 1):
        content = result.get("content", "")
        score = result.get("score", 0)
        source = _format_source_label(result)
        header = f"[{i}] (相关度: {score:.3f})"
        if source:
            header += f", {source}"
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


@dataclass
class RetrievalOutcome:
    """检索结果封装。"""

    items: List[dict]
    context: str
    retrieval_attempted: bool
    is_empty: bool


def build_query(
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        context_turns: int = 2,
) -> str:
    """
    构建检索 query（M0.2：拼接最近 context_turns 轮用户/助手原文 + 当前问）。
    """
    question = (question or "").strip()
    if not chat_history or context_turns <= 0:
        return question

    tail = chat_history[-(context_turns * 2):]
    parts = []
    for msg in tail:
        role = (msg.get("role") or "").strip()
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手"
        parts.append(f"{label}: {content}")
    if not parts:
        return question
    return "\n".join(parts) + f"\n用户: {question}"


def format_sources_payload(results: List[dict]) -> List[dict]:
    """格式化为 SSE sources.items 结构（§4.5 G）。"""
    items = []
    for i, result in enumerate(results, 1):
        content = result.get("content") or ""
        snippet = content[:200]
        if len(content) > 200:
            snippet += "..."
        page_number = result.get("page_number")
        items.append(
            {
                "index": i,
                "score": round(float(result.get("score") or 0), 4),
                "filename": result.get("filename") or "",
                "page_number": page_number,
                "chunk_id": result.get("chunk_id") or "",
                "snippet": snippet,
            }
        )
    return items


async def expand_context(
        results: List[dict],
        max_chars: Optional[int] = None,
) -> str:
    """
    方案 C：命中 child 后按 parent_chunk_id 加载节级 parent 文本进 Prompt。
    无 parent 的旧分块仍用 child 原文；同 parent 去重；总字符受 PARENT_CONTEXT_MAX_CHARS 限制。
    """
    if not results:
        return ""

    char_limit = max_chars or PROJECT_CONFIG.PARENT_CONTEXT_MAX_CHARS
    parent_ids = list(
        dict.fromkeys(
            (item.get("parent_chunk_id") or "").strip()
            for item in results
            if (item.get("parent_chunk_id") or "").strip()
        )
    )
    parent_map: Dict[str, DocumentChunk] = {}
    if parent_ids:
        rows = await DocumentChunk.filter(id__in=parent_ids, is_index=False).all()
        parent_map = {row.id: row for row in rows}

    parts: List[str] = []
    seen_parents: set = set()
    used_chars = 0
    block_index = 1

    for result in results:
        parent_id = (result.get("parent_chunk_id") or "").strip()
        score = float(result.get("score") or 0)
        source = _format_source_label(result)
        header = f"[{block_index}] (相关度: {score:.3f})"
        if source:
            header += f", {source}"

        if parent_id:
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)
            parent = parent_map.get(parent_id)
            content = ((parent.content if parent else None) or result.get("content") or "").strip()
        else:
            content = (result.get("content") or "").strip()

        if not content:
            continue

        remaining = char_limit - used_chars
        if remaining <= 0 and parts:
            break
        if len(content) > remaining:
            content = content[:remaining]

        parts.append(f"{header}\n{content}")
        used_chars += len(content)
        block_index += 1

    return "\n\n".join(parts)


def vector_fetch(
        query: str,
        knowledge_base_ids: List[str],
        fetch_top_k: int,
) -> List[dict]:
    """向量扩召回（Chroma）.
    """
    if not knowledge_base_ids or not is_embedding_configured():
        return []

    query_embedding = get_single_embedding(query)
    results = chroma_store.search(
        knowledge_base_ids,
        query_embedding,
        top_k=fetch_top_k,
    )
    return _filter_embedding_model_consistency(results)


def retrieve(
        question: str,
        knowledge_base_ids: List[str],
        *,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        fetch_top_k: Optional[int] = None,
        score_threshold: float = 0.0,
        rerank_enabled: bool = True,
        rerank_model: Optional[str] = None,
) -> RetrievalOutcome:
    """
    执行完整检索链路。

    Returns:
        RetrievalOutcome — retrieval_attempted 表示已选 KB 且尝试过检索。
    """
    kb_ids = knowledge_base_ids or []
    if not kb_ids:
        return RetrievalOutcome(
            items=[],
            context="",
            retrieval_attempted=False,
            is_empty=False,
        )

    if not is_embedding_configured():
        print("[rag] Embedding API 未配置，跳过知识库检索，使用通用对话模式")
        return RetrievalOutcome(
            items=[],
            context="",
            retrieval_attempted=False,
            is_empty=False,
        )

    fetch_k = fetch_top_k or PROJECT_CONFIG.RETRIEVAL_FETCH_TOP_K
    context_turns = PROJECT_CONFIG.RETRIEVAL_QUERY_CONTEXT_TURNS
    retrieval_q = build_query(question, chat_history, context_turns=context_turns)
    candidates = vector_fetch(retrieval_q, kb_ids, fetch_k)

    if score_threshold > 0:
        candidates = [
            item for item in candidates
            if float(item.get("score") or 0) >= score_threshold
        ]

    final_items = apply_rerank(
        retrieval_q,
        candidates,
        top_k,
        enabled=rerank_enabled,
        model=rerank_model,
    )
    context = format_context_from_results(final_items)
    is_empty = len(final_items) == 0

    return RetrievalOutcome(
        items=final_items,
        context=context,
        retrieval_attempted=True,
        is_empty=is_empty,
    )
