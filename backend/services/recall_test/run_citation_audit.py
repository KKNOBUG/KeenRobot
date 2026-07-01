# -*- coding: utf-8 -*-
"""
有源回答引用率批量审计 CLI（P2-3）。

用法（项目根目录 KeenRobot/）:
  PYTHONPATH=. python -m backend.services.recall_test.run_citation_audit
  PYTHONPATH=. python -m backend.services.recall_test.run_citation_audit --limit 500 --days 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.services.recall_test.citation_audit import run_citation_audit
from backend.services.recall_test.db import tortoise_session
from backend.services.recall_test.paths import DEFAULT_RESULTS_DIR


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="有源回答引用率 / orphan_digits 批量审计")
    parser.add_argument("--limit", type=int, default=200, help="最多扫描消息条数（默认 200）")
    parser.add_argument("--days", type=int, default=7, help="仅统计最近 N 天（0=不限）")
    parser.add_argument(
        "--output",
        default=None,
        help=f"结果 JSON（默认 {DEFAULT_RESULTS_DIR}/citation_<timestamp>.json）",
    )
    return parser


def _print_summary(report: dict) -> None:
    summary = report.get("summary") or {}
    print("\n========== Citation Audit ==========")
    print(f"output         : {report.get('output_file')}")
    print(f"sampled/checked: {summary.get('sampled')} / {summary.get('checked')}")
    print(f"citation_rate  : {summary.get('citation_rate')} (filename 或 page)")
    print(f"file+page rate : {summary.get('citation_file_and_page_rate')}")
    print(f"orphan_digits  : {summary.get('orphan_digits_rate')}")
    print("====================================\n")


async def _async_main(args: argparse.Namespace) -> int:
    async with tortoise_session():
        days = args.days if args.days > 0 else None
        report = await run_citation_audit(
            limit=args.limit,
            days=days,
            output_path=args.output,
        )

    _print_summary(report)
    if args.output is None:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\n[citation_audit] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
