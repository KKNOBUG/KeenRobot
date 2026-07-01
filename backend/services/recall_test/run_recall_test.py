# -*- coding: utf-8 -*-
"""
RAG 检索召回离线评测 CLI。

用法（在项目根目录 KeenRobot 下）:
  PYTHONPATH=. python -m backend.services.recall_test.run_recall_test
  PYTHONPATH=. python -m backend.services.recall_test.run_recall_test --tag 多轮 --scenario recall
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.services.recall_test.db import tortoise_session
from backend.services.recall_test.paths import (
    DEFAULT_QUESTIONS_PATH,
    DEFAULT_QUESTIONS_TEMPLATE_PATH,
    DEFAULT_RESULTS_DIR,
)
from backend.services.recall_test.runner import run_recall_eval


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG 检索召回离线评测（仅 retrieve，不含 LLM 回答）")
    parser.add_argument(
        "--questions",
        default=None,
        help=f"评测集 JSONL 路径（默认 {DEFAULT_QUESTIONS_PATH}，不存在则回退 template）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"结果 JSON 路径（默认 {DEFAULT_RESULTS_DIR}/recall_<timestamp>.json）",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="仅跑 tags 含该值的样本（如 多轮、空召回、多库）",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        choices=("balanced", "precision", "recall"),
        help="覆盖 RETRIEVAL_SCENARIO 预设（fetch/top_k/threshold）",
    )
    parser.add_argument(
        "--model-config-id",
        default=None,
        help="使用指定 ModelConfig 的 top_k / threshold / rerank 配置",
    )
    return parser


def _print_summary(report: dict) -> None:
    summary = report.get("summary") or {}
    print("\n========== RAG Recall Test ==========")
    print(f"questions : {report.get('questions_file')}")
    if report.get("used_template_fallback"):
        print(f"注意      : 使用了 template，建议复制为 {DEFAULT_QUESTIONS_PATH}")
    print(f"scenario  : {report.get('retrieval_scenario')}")
    print(f"output    : {report.get('output_file')}")
    print("-------------------------------------")
    print(f"total           : {summary.get('total')}")
    print(f"errors          : {summary.get('errors')}")
    print(f"recall_rate     : {summary.get('recall_rate')}")
    print(f"hit_at_k_rate   : {summary.get('hit_at_k_rate')}")
    print(f"empty_accuracy  : {summary.get('empty_accuracy')}")
    print(f"multi_kb_rate   : {summary.get('multi_kb_coverage_rate')}")
    latency = summary.get("latency_ms") or {}
    print(f"latency p50/p95 : {latency.get('p50')} / {latency.get('p95')} ms")
    print("=====================================\n")


async def _async_main(args: argparse.Namespace) -> int:
    async with tortoise_session():
        report = await run_recall_eval(
            questions_path=args.questions,
            output_path=args.output,
            tag=args.tag,
            scenario=args.scenario,
            model_config_id=args.model_config_id,
        )

    _print_summary(report)

    if args.output is None:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

    errors = (report.get("summary") or {}).get("errors") or 0
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except FileNotFoundError as exc:
        print(f"[recall_test] {exc}", file=sys.stderr)
        print(
            f"[recall_test] 请先执行: cp {DEFAULT_QUESTIONS_TEMPLATE_PATH} {DEFAULT_QUESTIONS_PATH}",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:
        print(f"[recall_test] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n[recall_test] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
