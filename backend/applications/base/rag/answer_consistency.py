# -*- coding: utf-8 -*-
"""有源回答轻量一致性检查（P1-5）：日志/抽检，不阻塞线上。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_DIGIT_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def check_answer_source_alignment(
        answer: str,
        sources_items: Optional[List[dict]],
        *,
        retrieval_empty: bool = False,
) -> Dict[str, Any]:
    """
    检查回答与 sources 的对齐情况（规则级，供日志与评测脚本复用）。

    Returns:
        cites_filename: 是否出现 sources 中的文件名
        cites_page: 是否出现 sources 中的页码
        orphan_digits: 出现在回答但不在 snippet 中的数字（疑似幻觉信号）
    """
    text = (answer or "").strip()
    if retrieval_empty or not sources_items or not text:
        return {"checked": False}

    filenames = {(item.get("filename") or "").strip() for item in sources_items}
    filenames.discard("")
    pages = {item.get("page_number") for item in sources_items if item.get("page_number") is not None}

    cites_filename = any(name in text for name in filenames)
    cites_page = any(str(page) in text for page in pages)

    snippet_blob = " ".join((item.get("snippet") or "") for item in sources_items)
    answer_digits = set(_DIGIT_PATTERN.findall(text))
    snippet_digits = set(_DIGIT_PATTERN.findall(snippet_blob))
    orphan_digits = sorted(answer_digits - snippet_digits)

    return {
        "checked": True,
        "cites_filename": cites_filename,
        "cites_page": cites_page,
        "orphan_digits": orphan_digits,
        "source_count": len(sources_items),
    }
