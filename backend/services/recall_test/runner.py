# -*- coding: utf-8 -*-
"""执行检索召回评测。"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.applications.base.rag.retriever import format_sources_payload, retrieve
from backend.applications.knowledge_base.models.knowledge_base_model import KnowledgeBase
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.services.llm_connection import resolve_chat_llm_params
from backend.configure import PROJECT_CONFIG
from backend.configure.retrieval_presets import apply_retrieval_scenario, resolve_retrieval_scenario
from backend.services.recall_test.dataset import EvalCase, load_eval_cases
from backend.services.recall_test.metrics import CaseResult, keyword_hit, summarize_results
from backend.services.recall_test.paths import ensure_results_dir, resolve_questions_path


async def _load_kb_name_index() -> Dict[str, str]:
    rows = await KnowledgeBase.all().only("id", "knowledge_name")
    return {row.knowledge_name: row.id for row in rows if row.knowledge_name}


def _resolve_kb_ids(kb_names: Sequence[str], name_index: Dict[str, str]) -> Tuple[List[str], List[str]]:
    kb_ids: List[str] = []
    missing: List[str] = []
    for name in kb_names:
        kb_id = name_index.get(name)
        if not kb_id:
            missing.append(name)
        elif kb_id not in kb_ids:
            kb_ids.append(kb_id)
    return kb_ids, missing


def _evaluate_case(
        case: EvalCase,
        *,
        name_index: Dict[str, str],
        retrieval_params: Dict[str, Any],
) -> CaseResult:
    start = time.perf_counter()
    kb_ids, missing_names = _resolve_kb_ids(case.kb_names, name_index)

    if missing_names:
        return CaseResult(
            index=case.index,
            question=case.question,
            kb_names=case.kb_names,
            kb_ids=kb_ids,
            tags=case.tags,
            expect_empty=case.expect_empty,
            expect_multi_kb=case.expect_multi_kb,
            expected_keywords=case.expected_keywords,
            retrieval_empty=True,
            source_count=0,
            kb_ids_in_sources=[],
            hit_at_k=None,
            multi_kb_ok=None,
            empty_ok=None,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            missing_kb_names=missing_names,
            error=f"知识库名称未找到: {', '.join(missing_names)}",
        )

    outcome = retrieve(
        case.question,
        kb_ids,
        chat_history=case.chat_history,
        top_k=int(retrieval_params.get("top_k") or 6),
        fetch_top_k=int(retrieval_params.get("fetch_top_k") or PROJECT_CONFIG.RETRIEVAL_FETCH_TOP_K),
        score_threshold=float(retrieval_params.get("score_threshold") or 0),
        rerank_enabled=bool(retrieval_params.get("rerank_enabled", True)),
        rerank_model=retrieval_params.get("rerank_model"),
    )
    sources = format_sources_payload(outcome.items)
    snippets = [item.get("snippet") or "" for item in sources]
    kb_ids_in_sources = sorted(
        {(item.get("kb_id") or "").strip() for item in sources if (item.get("kb_id") or "").strip()}
    )
    retrieval_empty = outcome.retrieval_attempted and outcome.is_empty

    hit_at_k = None
    if not case.expect_empty and case.expected_keywords:
        hit_at_k = keyword_hit(snippets, case.expected_keywords) if not retrieval_empty else False

    multi_kb_ok = None
    if case.expect_multi_kb and len(kb_ids) > 1:
        multi_kb_ok = all(kb_id in kb_ids_in_sources for kb_id in kb_ids)

    empty_ok = case.expect_empty and retrieval_empty if case.expect_empty else None

    return CaseResult(
        index=case.index,
        question=case.question,
        kb_names=case.kb_names,
        kb_ids=kb_ids,
        tags=case.tags,
        expect_empty=case.expect_empty,
        expect_multi_kb=case.expect_multi_kb,
        expected_keywords=case.expected_keywords,
        retrieval_empty=retrieval_empty,
        source_count=len(sources),
        kb_ids_in_sources=kb_ids_in_sources,
        hit_at_k=hit_at_k,
        multi_kb_ok=multi_kb_ok,
        empty_ok=empty_ok,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


async def run_recall_eval(
        *,
        questions_path: str | None = None,
        output_path: str | None = None,
        tag: Optional[str] = None,
        scenario: Optional[str] = None,
        model_config_id: Optional[str] = None,
) -> Dict[str, Any]:
    """跑检索召回评测并写入 JSON 报告（仅 retrieve，不含 LLM 生成）。"""
    path = resolve_questions_path(questions_path)
    cases = load_eval_cases(path, tag=tag)

    model_config = None
    if model_config_id:
        model_config = await ModelConfig.get_or_none(id=model_config_id)
        if model_config is None:
            raise ValueError(f"ModelConfig 不存在: {model_config_id}")

    retrieval_params = resolve_chat_llm_params(model_config)
    if scenario:
        retrieval_params = apply_retrieval_scenario(retrieval_params, scenario)

    name_index = await _load_kb_name_index()
    case_results = [
        _evaluate_case(case, name_index=name_index, retrieval_params=retrieval_params)
        for case in cases
    ]

    if output_path:
        out = Path(output_path).expanduser()
    else:
        out = ensure_results_dir() / f"recall_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "questions_file": str(path),
        "used_template_fallback": path.name == "questions.template.jsonl",
        "tag_filter": tag,
        "retrieval_scenario": resolve_retrieval_scenario(scenario),
        "retrieval_params": {
            "top_k": retrieval_params.get("top_k"),
            "fetch_top_k": retrieval_params.get("fetch_top_k"),
            "score_threshold": retrieval_params.get("score_threshold"),
            "rerank_enabled": retrieval_params.get("rerank_enabled"),
            "rerank_model": retrieval_params.get("rerank_model"),
        },
        "env_flags": {
            "RETRIEVAL_QUERY_ENHANCE_ENABLED": PROJECT_CONFIG.RETRIEVAL_QUERY_ENHANCE_ENABLED,
            "RETRIEVAL_EMPTY_RETRY_ENABLED": PROJECT_CONFIG.RETRIEVAL_EMPTY_RETRY_ENABLED,
            "RETRIEVAL_MULTI_QUERY_FUSION_ENABLED": PROJECT_CONFIG.RETRIEVAL_MULTI_QUERY_FUSION_ENABLED,
            "RETRIEVAL_MULTI_QUERY_MAX": PROJECT_CONFIG.RETRIEVAL_MULTI_QUERY_MAX,
            "RETRIEVAL_MIN_HITS_PER_KB": PROJECT_CONFIG.RETRIEVAL_MIN_HITS_PER_KB,
        },
        "summary": summarize_results(case_results),
        "cases": [item.to_dict() for item in case_results],
        "output_file": str(out),
    }
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
