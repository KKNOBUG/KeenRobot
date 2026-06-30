# -*- coding: utf-8 -*-
"""Rerank 精排（F）：OpenAI 兼容 / DashScope 原生；未配置 Key 时降级为向量顺序。"""

from typing import List, Optional

import requests

from backend.configure import PROJECT_CONFIG, LOGGER

_DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-api/v1"


def is_rerank_configured() -> bool:
    return bool((PROJECT_CONFIG.RERANK_API_KEY or "").strip())


def apply_rerank(
        query: str,
        candidates: List[dict],
        top_k: int,
        *,
        enabled: bool = True,
        model: Optional[str] = None,
) -> List[dict]:
    """精排并截断；失败或未启用时取向量候选前 top_k。"""
    if not candidates:
        return []

    if not enabled or not is_rerank_configured():
        if len(candidates) > top_k:
            LOGGER.info("[rag] RERANK_API_KEY 未配置，跳过 Rerank，使用向量检索顺序")
        return candidates[:top_k]

    try:
        ranked = _rerank_http(query, candidates, top_k, model)
        return ranked if ranked else candidates[:top_k]
    except Exception as exc:
        LOGGER.warning("[rag] Rerank 失败，降级为向量顺序: %s", exc)
        return candidates[:top_k]


def _rerank_http(
        query: str,
        candidates: List[dict],
        top_k: int,
        model: Optional[str],
) -> List[dict]:
    api_key = (PROJECT_CONFIG.RERANK_API_KEY or "").strip()
    model_name = (model or PROJECT_CONFIG.RERANK_MODEL or "qwen3-rerank").strip()
    base = (PROJECT_CONFIG.RERANK_BASE_URL or _DEFAULT_BASE).strip().rstrip("/")
    documents = [item.get("content") or "" for item in candidates]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if "/services/rerank" in base:
        url = base if base.endswith("text-rerank") else f"{base}/text-rerank/text-rerank"
        payload = {
            "model": model_name,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": top_k, "return_documents": False},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Rerank API 失败: {resp.text} (url={url})")
        results = (resp.json().get("output") or {}).get("results") or []
        ranked = []
        for row in results:
            idx = row.get("index")
            if idx is None or idx < 0 or idx >= len(candidates):
                continue
            item = dict(candidates[idx])
            if row.get("relevance_score") is not None:
                item["score"] = float(row["relevance_score"])
            ranked.append(item)
        return ranked[:top_k]

    url = base if base.endswith("/reranks") else f"{base}/reranks"
    payload = {
        "model": model_name,
        "query": query,
        "documents": documents,
        "top_n": top_k,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Rerank API 失败: {resp.text} (url={url})")

    body = resp.json()
    rows = body.get("results") or body.get("data") or []
    ranked = []
    for row in rows:
        idx = row.get("index")
        if idx is None:
            idx = row.get("document", {}).get("index")
        if idx is None or idx < 0 or idx >= len(candidates):
            continue
        item = dict(candidates[int(idx)])
        score = row.get("relevance_score")
        if score is None:
            score = row.get("score")
        if score is not None:
            item["score"] = float(score)
        ranked.append(item)
    return ranked[:top_k]
