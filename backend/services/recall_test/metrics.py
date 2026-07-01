# -*- coding: utf-8 -*-
"""召回评测指标聚合。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[rank], 2)


def keyword_hit(snippets: List[str], keywords: List[str]) -> bool:
    if not keywords:
        return True
    blob = "\n".join(snippets).lower()
    return any(keyword.lower() in blob for keyword in keywords)


@dataclass
class CaseResult:
    index: int
    question: str
    kb_names: List[str]
    kb_ids: List[str]
    tags: List[str]
    expect_empty: bool
    expect_multi_kb: bool
    expected_keywords: List[str]
    retrieval_empty: bool
    source_count: int
    kb_ids_in_sources: List[str]
    hit_at_k: Optional[bool]
    multi_kb_ok: Optional[bool]
    empty_ok: Optional[bool]
    latency_ms: float
    missing_kb_names: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "question": self.question,
            "kb_names": self.kb_names,
            "kb_ids": self.kb_ids,
            "tags": self.tags,
            "expect_empty": self.expect_empty,
            "expect_multi_kb": self.expect_multi_kb,
            "expected_keywords": self.expected_keywords,
            "retrieval_empty": self.retrieval_empty,
            "source_count": self.source_count,
            "kb_ids_in_sources": self.kb_ids_in_sources,
            "hit_at_k": self.hit_at_k,
            "multi_kb_ok": self.multi_kb_ok,
            "empty_ok": self.empty_ok,
            "latency_ms": self.latency_ms,
            "missing_kb_names": self.missing_kb_names,
            "error": self.error,
        }


def summarize_results(cases: List[CaseResult]) -> Dict[str, Any]:
    latencies = [item.latency_ms for item in cases if item.error is None]

    should_hit = [c for c in cases if not c.expect_empty and c.error is None]
    empty_cases = [c for c in cases if c.expect_empty and c.error is None]
    hit_cases = [c for c in should_hit if c.expected_keywords]
    multi_kb_cases = [c for c in cases if c.expect_multi_kb and c.error is None]

    recall_rate = _ratio(should_hit, lambda c: not c.retrieval_empty)
    hit_at_k_rate = _ratio(hit_cases, lambda c: bool(c.hit_at_k))
    empty_accuracy = _ratio(empty_cases, lambda c: bool(c.empty_ok))
    multi_kb_rate = _ratio(multi_kb_cases, lambda c: bool(c.multi_kb_ok))

    by_tag: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        for tag in case.tags or ["未分类"]:
            bucket = by_tag.setdefault(tag, {"total": 0, "errors": 0})
            bucket["total"] += 1
            if case.error:
                bucket["errors"] += 1

    return {
        "total": len(cases),
        "errors": sum(1 for c in cases if c.error),
        "recall_rate": recall_rate,
        "hit_at_k_rate": hit_at_k_rate,
        "empty_accuracy": empty_accuracy,
        "multi_kb_coverage_rate": multi_kb_rate,
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "avg": round(sum(latencies) / len(latencies), 2) if latencies else None,
        },
        "by_tag_counts": by_tag,
    }


def _ratio(items: List[CaseResult], predicate) -> Optional[float]:
    if not items:
        return None
    hits = sum(1 for item in items if predicate(item))
    return round(hits / len(items), 4)
