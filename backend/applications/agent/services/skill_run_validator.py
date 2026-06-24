# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_validator.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.applications.agent.services.workspace_service import WorkspaceService


def _missing(
        step: Dict[str, Any],
        reason: str,
) -> Dict[str, Any]:
    return {
        "key": step.get("key"),
        "label": step.get("label") or step.get("key"),
        "type": step.get("type"),
        "reason": reason,
    }


def validate_run_inputs(
        workspace: WorkspaceService,
        input_schema: Optional[Dict[str, Any]],
        input_data: Optional[Dict[str, Any]],
) -> tuple[bool, List[Dict[str, Any]]]:
    """按 DB input_schema 校验 Run 工作区输入。"""
    schema = input_schema or {}
    steps = schema.get("wizard_steps") or []
    data = dict(input_data or {})
    missing: List[Dict[str, Any]] = []
    run_root = workspace.root

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_type = step.get("type")
        key = step.get("key")
        required = step.get("required", True)
        label = step.get("label") or key

        if step_type == "confirm":
            if required and not data.get(key):
                missing.append(_missing(step, "尚未确认"))
            continue

        if step_type == "text":
            value = data.get(key)
            if required and (value is None or str(value).strip() == ""):
                missing.append(_missing(step, "缺少文本输入"))
            continue

        if step_type == "choice":
            value = data.get(key)
            options = step.get("options") or []
            options_source = step.get("options_source")
            if value is not None and str(value).strip() != "":
                if options and value not in options:
                    missing.append(_missing(step, "选项无效"))
                continue
            if options_source:
                pattern = options_source.replace("\\", "/")
                base = run_root
                matches = list(base.glob(pattern))
                file_matches = [p for p in matches if p.is_file()]
                if required and not file_matches and not value:
                    missing.append(_missing(step, f"未找到匹配文件: {options_source}"))
                continue
            if required and (value is None or str(value).strip() == ""):
                missing.append(_missing(step, "缺少选择项"))
            continue

        if step_type == "file":
            try:
                rel = workspace.step_target_path(step, schema)
                target = workspace.resolve_safe_path(rel)
            except ValueError as exc:
                missing.append(_missing(step, str(exc)))
                continue
            if required and (not target.is_file()):
                missing.append(_missing(step, f"缺少文件: {label}"))
            continue

        if step_type == "dir":
            try:
                rel = workspace.step_target_path(step, schema)
                target = workspace.resolve_safe_path(rel)
            except ValueError as exc:
                missing.append(_missing(step, str(exc)))
                continue
            if required:
                if not target.is_dir():
                    missing.append(_missing(step, f"缺少目录: {label}"))
                elif not any(target.iterdir()):
                    missing.append(_missing(step, f"目录为空: {label}"))
            continue

    return len(missing) == 0, missing


def list_output_files(output_dir: Path, *, prefix: str = "") -> List[Dict[str, Any]]:
    """递归列出产物文件。"""
    if not output_dir.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(output_dir).as_posix()
        items.append(
            {
                "path": rel,
                "name": path.name,
                "size": path.stat().st_size,
            }
        )
    return items
