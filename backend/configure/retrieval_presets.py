# -*- coding: utf-8 -*-
"""RAG 检索分场景参数预设（P1-7）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from backend.configure import PROJECT_CONFIG

# score_threshold 为 None 表示沿用 ModelConfig / env 已解析值
RETRIEVAL_SCENARIO_PRESETS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "fetch_top_k": 30,
        "top_k": 6,
        "score_threshold": None,
    },
    "precision": {
        "fetch_top_k": 24,
        "top_k": 4,
        "score_threshold": 0.5,
    },
    "recall": {
        "fetch_top_k": 40,
        "top_k": 8,
        "score_threshold": 0.4,
    },
}


def resolve_retrieval_scenario(scenario: Optional[str] = None) -> str:
    name = (scenario or PROJECT_CONFIG.RETRIEVAL_SCENARIO or "balanced").strip().lower()
    if name not in RETRIEVAL_SCENARIO_PRESETS:
        return "balanced"
    return name


def apply_retrieval_scenario(
        chat_params: Dict[str, Any],
        scenario: Optional[str] = None,
) -> Dict[str, Any]:
    """在 resolve_chat_llm_params 结果上叠加场景预设（fetch/top_k/threshold）。"""
    preset = RETRIEVAL_SCENARIO_PRESETS[resolve_retrieval_scenario(scenario)]
    merged = dict(chat_params)
    merged["fetch_top_k"] = preset["fetch_top_k"]
    merged["top_k"] = preset["top_k"]
    threshold = preset.get("score_threshold")
    if threshold is not None:
        merged["score_threshold"] = threshold
    return merged
