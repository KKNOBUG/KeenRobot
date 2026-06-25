# -*- coding: utf-8 -*-
"""SSE 流式事件辅助（process_trace 合并等）。"""
from typing import List


def merge_process_step(process_trace: List[dict], step: dict) -> None:
    """按 MCP/Skill 步骤键去重更新 process_trace（原地修改）。"""
    if not step:
        return
    step_type = step.get("type")
    for idx, existing in enumerate(process_trace):
        if step_type == "mcp" and (
            existing.get("type") == "mcp"
            and existing.get("tool") == step.get("tool")
            and existing.get("server") == step.get("server")
        ):
            process_trace[idx] = step
            return
        if step_type == "skill" and (
            existing.get("type") == "skill"
            and existing.get("name") == step.get("name")
            and existing.get("skill_id") == step.get("skill_id")
        ):
            process_trace[idx] = step
            return
    process_trace.append(step)
