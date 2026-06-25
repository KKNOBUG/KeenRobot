# -*- coding: utf-8 -*-
"""Skill 向导收集面板状态辅助。"""
from typing import Any, Dict, Optional


def freeze_intake_as_submitted(
        intake: Optional[Dict[str, Any]],
        input_schema: Optional[dict],
) -> Dict[str, Any]:
    """将收集面板标记为已提交（幂等）。"""
    frozen = dict(intake or {})
    if frozen.get("phase") in ("submitted", "cancelled"):
        return frozen
    steps = (input_schema or {}).get("wizard_steps") or []
    frozen["phase"] = "submitted"
    if steps:
        frozen["step_index"] = len(steps) - 1
    frozen.pop("run_summary", None)
    frozen.pop("process_trace", None)
    return frozen
