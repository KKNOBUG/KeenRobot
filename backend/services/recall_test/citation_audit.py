# -*- coding: utf-8 -*-
"""有源回答引用率批量审计（P2-3）。"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.applications.base.rag.answer_consistency import check_answer_source_alignment
from backend.applications.conversation.models.conversation_model import Message
from backend.configure import PROJECT_CONFIG
from backend.enums.chat_session_enum import ChatMessageRole
from backend.services.recall_test.paths import ensure_results_dir


async def run_citation_audit(
        *,
        limit: int = 200,
        days: Optional[int] = 7,
        output_path: str | None = None,
) -> Dict[str, Any]:
    """
    扫描库内「有 sources、非空召回」的助手消息，统计引用率与 orphan_digits。
    """
    query = Message.filter(
        role=ChatMessageRole.ASSISTANT,
        sources_json__not_isnull=True,
    ).exclude(retrieval_empty=True)

    if days and days > 0:
        since = datetime.now() - timedelta(days=days)
        query = query.filter(created_time__gte=since)

    rows: List[Message] = await query.order_by("-id").limit(limit).all()

    items: List[Dict[str, Any]] = []
    cites_any = 0
    cites_both = 0
    orphan_count = 0
    checked = 0

    for row in rows:
        sources = row.sources_json or []
        if not sources or not (row.content or "").strip():
            continue

        report = check_answer_source_alignment(
            row.content,
            sources,
            retrieval_empty=False,
        )
        if not report.get("checked"):
            continue

        checked += 1
        has_file = bool(report.get("cites_filename"))
        has_page = bool(report.get("cites_page"))
        orphans = report.get("orphan_digits") or []

        if has_file or has_page:
            cites_any += 1
        if has_file and has_page:
            cites_both += 1
        if orphans:
            orphan_count += 1

        items.append(
            {
                "message_id": row.id,
                "conversation_id": row.conversation_id,
                "cites_filename": has_file,
                "cites_page": has_page,
                "orphan_digits": orphans,
                "source_count": report.get("source_count"),
            }
        )

    summary = {
        "sampled": len(rows),
        "checked": checked,
        "citation_rate": round(cites_any / checked, 4) if checked else None,
        "citation_file_and_page_rate": round(cites_both / checked, 4) if checked else None,
        "orphan_digits_rate": round(orphan_count / checked, 4) if checked else None,
    }

    result: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "limit": limit,
        "days": days,
        "answer_consistency_log_enabled": PROJECT_CONFIG.ANSWER_CONSISTENCY_LOG_ENABLED,
        "summary": summary,
        "items": items,
    }

    if output_path:
        out = Path(output_path).expanduser()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = ensure_results_dir() / f"citation_{stamp}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result["output_file"] = str(out)
    return result
