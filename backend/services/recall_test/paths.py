# -*- coding: utf-8 -*-
"""评测数据与结果路径。"""
from pathlib import Path

from backend.configure import PROJECT_CONFIG

EVAL_DIR = Path(PROJECT_CONFIG.OUTPUT_DIR) / "eval"
DEFAULT_QUESTIONS_TEMPLATE_PATH = EVAL_DIR / "questions.template.jsonl"
DEFAULT_QUESTIONS_PATH = EVAL_DIR / "questions.jsonl"
DEFAULT_RESULTS_DIR = EVAL_DIR / "results"


def resolve_questions_path(path: str | None = None, *, allow_template: bool = True) -> Path:
    if path:
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(f"评测集不存在: {candidate}")
        return candidate

    if DEFAULT_QUESTIONS_PATH.is_file():
        return DEFAULT_QUESTIONS_PATH

    if allow_template and DEFAULT_QUESTIONS_TEMPLATE_PATH.is_file():
        return DEFAULT_QUESTIONS_TEMPLATE_PATH

    raise FileNotFoundError(
        f"未找到评测集。请复制 {DEFAULT_QUESTIONS_TEMPLATE_PATH} "
        f"为 {DEFAULT_QUESTIONS_PATH} 或通过 --questions 指定路径。"
    )


def ensure_results_dir() -> Path:
    DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_RESULTS_DIR
