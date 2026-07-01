# -*- coding: utf-8 -*-
"""RAG 检索离线召回评测（非业务运行时 CLI）。"""
from backend.services.recall_test.citation_audit import run_citation_audit
from backend.services.recall_test.paths import (
    DEFAULT_QUESTIONS_PATH,
    DEFAULT_QUESTIONS_TEMPLATE_PATH,
    DEFAULT_RESULTS_DIR,
)
from backend.services.recall_test.runner import run_recall_eval

__all__ = (
    "run_recall_eval",
    "run_citation_audit",
    "DEFAULT_QUESTIONS_PATH",
    "DEFAULT_QUESTIONS_TEMPLATE_PATH",
    "DEFAULT_RESULTS_DIR",
)
