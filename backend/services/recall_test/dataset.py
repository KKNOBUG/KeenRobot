# -*- coding: utf-8 -*-
"""评测集加载与样本构造。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EvalCase:
    """单条评测样本。"""

    index: int
    question: str
    kb_names: List[str]
    expected_keywords: List[str] = field(default_factory=list)
    expect_empty: bool = False
    expect_multi_kb: bool = False
    followup: bool = False
    prior_user: str = ""
    tags: List[str] = field(default_factory=list)
    note: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def chat_history(self) -> Optional[List[Dict[str, str]]]:
        if not self.followup:
            return None
        prior = (self.prior_user or "").strip()
        if not prior:
            return None
        return [
            {"role": "user", "content": prior},
            {"role": "assistant", "content": "（评测占位回复，仅用于构造多轮上下文）"},
        ]


def load_eval_cases(path: Path, *, tag: Optional[str] = None) -> List[EvalCase]:
    cases: List[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} JSON 解析失败: {exc}") from exc

            question = (row.get("question") or "").strip()
            kb_names = row.get("kb_names") or []
            if not question:
                raise ValueError(f"{path}:{line_no} 缺少 question")
            if not kb_names:
                raise ValueError(f"{path}:{line_no} 缺少 kb_names")

            case = EvalCase(
                index=len(cases) + 1,
                question=question,
                kb_names=[str(name).strip() for name in kb_names if str(name).strip()],
                expected_keywords=[str(k).strip() for k in (row.get("expected_keywords") or []) if str(k).strip()],
                expect_empty=bool(row.get("expect_empty")),
                expect_multi_kb=bool(row.get("expect_multi_kb")),
                followup=bool(row.get("followup")),
                prior_user=(row.get("prior_user") or "").strip(),
                tags=[str(t).strip() for t in (row.get("tags") or []) if str(t).strip()],
                note=(row.get("note") or "").strip(),
                raw=row,
            )
            if tag and tag not in case.tags:
                continue
            cases.append(case)

    if not cases:
        hint = f"（tag={tag!r} 过滤后为空）" if tag else ""
        raise ValueError(f"评测集无有效样本{hint}: {path}")
    return cases
