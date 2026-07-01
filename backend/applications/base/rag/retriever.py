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
                "kb_id": result.get("kb_id") or "",
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


def _result_dedupe_key(item: dict) -> str:
    return (item.get("chunk_id") or item.get("id") or "").strip()


def _resolve_fetch_per_kb(fetch_top_k: int, kb_count: int) -> int:
    if kb_count <= 1:
        return fetch_top_k
    configured = PROJECT_CONFIG.RETRIEVAL_FETCH_PER_KB
    if configured and configured > 0:
        return configured
    return max(10, (fetch_top_k + kb_count - 1) // kb_count)


def _effective_min_hits_per_kb(top_k: int, kb_count: int, configured_min: int) -> int:
    if kb_count <= 1 or configured_min <= 0 or top_k <= 0:
        return 0
    capped = min(configured_min, top_k)
    if kb_count * capped > top_k:
        return max(1, top_k // kb_count)
    return capped


def apply_kb_quota(
        ranked: List[dict],
        knowledge_base_ids: List[str],
        top_k: int,
) -> List[dict]:
    """多库终选：每库保底 min 条，余量按全局分数填充。"""
    kb_ids = [kb for kb in knowledge_base_ids if kb]
    if len(kb_ids) <= 1 or top_k <= 0:
        return ranked[:top_k]

    min_per_kb = _effective_min_hits_per_kb(
        top_k,
        len(kb_ids),
        PROJECT_CONFIG.RETRIEVAL_MIN_HITS_PER_KB,
    )
    max_per_kb = PROJECT_CONFIG.RETRIEVAL_MAX_HITS_PER_KB or 0

    by_kb: Dict[str, List[dict]] = {kb: [] for kb in kb_ids}
    for item in ranked:
        kb = (item.get("kb_id") or "").strip()
        if kb in by_kb:
            by_kb[kb].append(item)

    selected: List[dict] = []
    selected_keys: set[str] = set()

    if min_per_kb > 0:
        for kb in kb_ids:
            taken = 0
            for item in by_kb.get(kb, []):
                key = _result_dedupe_key(item)
                if key and key in selected_keys:
                    continue
                selected.append(item)
                if key:
                    selected_keys.add(key)
                taken += 1
                if taken >= min_per_kb or len(selected) >= top_k:
                    break

    for item in ranked:
        if len(selected) >= top_k:
            break
        key = _result_dedupe_key(item)
        if key and key in selected_keys:
            continue
        kb = (item.get("kb_id") or "").strip()
        if max_per_kb > 0:
            kb_count = sum(1 for s in selected if (s.get("kb_id") or "").strip() == kb)
            if kb_count >= max_per_kb:
                continue
        selected.append(item)
        if key:
            selected_keys.add(key)

    return selected[:top_k]


def vector_fetch(
        query: str,
        knowledge_base_ids: List[str],
        fetch_top_k: int,
) -> List[dict]:
    """向量扩召回（Chroma）；多库时分库 query 再合并去重。"""
    if not knowledge_base_ids or not is_embedding_configured():
        return []

    query_embedding = get_single_embedding(query)
    kb_ids = list(dict.fromkeys(knowledge_base_ids))

    if len(kb_ids) == 1:
        results = chroma_store.search(kb_ids, query_embedding, top_k=fetch_top_k)
        return _filter_embedding_model_consistency(results)

    per_kb = _resolve_fetch_per_kb(fetch_top_k, len(kb_ids))
    merged: List[dict] = []
    seen_keys: set[str] = set()
    for kb_id in kb_ids:
        hits = chroma_store.search([kb_id], query_embedding, top_k=per_kb)
        for item in _filter_embedding_model_consistency(hits):
            key = _result_dedupe_key(item)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            merged.append(item)

    merged.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return merged


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

    rerank_k = top_k
    if len(kb_ids) > 1 and candidates:
        rerank_k = min(len(candidates), max(top_k, top_k * len(kb_ids)))

    final_items = apply_rerank(
        retrieval_q,
        candidates,
        rerank_k,
        enabled=rerank_enabled,
        model=rerank_model,
    )
    if len(kb_ids) > 1:
        final_items = apply_kb_quota(final_items, kb_ids, top_k)
    context = format_context_from_results(final_items)
    is_empty = len(final_items) == 0

    return RetrievalOutcome(
        items=final_items,
        context=context,
        retrieval_attempted=True,
        is_empty=is_empty,
    )
