# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_file_tools.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_READ_BYTES = 256 * 1024
MAX_WRITE_BYTES = 512 * 1024
MAX_GLOB_RESULTS = 100

SKILL_READ_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_read",
        "description": "读取工作区内相对路径的文件内容（只读）。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作区根目录的文件路径",
                }
            },
            "required": ["path"],
        },
    },
}

SKILL_GLOB_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_glob",
        "description": "按 glob 模式列出工作区内的文件（只读）。",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "glob 模式，如 .skill_snapshot/rules/*.md",
                }
            },
            "required": ["pattern"],
        },
    },
}

SKILL_WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_write",
        "description": "写入文件到 output 目录（仅 Run 模式）。路径须位于 output/ 下。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对路径，须位于 output/ 下",
                },
                "content": {
                    "type": "string",
                    "description": "写入内容",
                },
            },
            "required": ["path", "content"],
        },
    },
}


def _resolve_safe_path(cwd: Path, relative_path: str) -> Path:
    rel = (relative_path or "").strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("非法路径")
    target = (cwd / rel).resolve()
    cwd_resolved = cwd.resolve()
    if not str(target).startswith(str(cwd_resolved)):
        raise ValueError("路径超出 Skill 工作区")
    return target


def _resolve_write_path(cwd: Path, relative_path: str, output_prefix: str) -> Path:
    target = _resolve_safe_path(cwd, relative_path)
    prefix = output_prefix.strip("/").rstrip("/") + "/"
    rel = target.relative_to(cwd.resolve()).as_posix()
    if not rel.startswith(prefix):
        raise ValueError(f"写入路径必须在 {output_prefix}/ 下")
    return target


def execute_skill_tool(
        cwd: Path,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        output_prefix: Optional[str] = "output",
) -> str:
    if tool_name == "skill_read":
        path = arguments.get("path") or ""
        target = _resolve_safe_path(cwd, path)
        if not target.is_file():
            raise FileNotFoundError(f"文件不存在: {path}")
        data = target.read_bytes()
        if len(data) > MAX_READ_BYTES:
            text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
            return text + f"\n...(已截断，最大 {MAX_READ_BYTES} 字节)"
        return target.read_text(encoding="utf-8")

    if tool_name == "skill_glob":
        pattern = (arguments.get("pattern") or "").strip()
        if not pattern or ".." in pattern:
            raise ValueError("非法 glob 模式")
        matches = sorted(
            p.relative_to(cwd).as_posix()
            for p in cwd.glob(pattern)
            if p.is_file()
        )[:MAX_GLOB_RESULTS]
        if not matches:
            return "未匹配到文件"
        return "\n".join(matches)

    if tool_name == "skill_write":
        path = arguments.get("path") or ""
        content = arguments.get("content") or ""
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ValueError(f"写入内容超过 {MAX_WRITE_BYTES // 1024}KB 限制")
        target = _resolve_write_path(cwd, path, output_prefix or "output")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {path}（{len(content)} 字符）"

    raise ValueError(f"未知工具: {tool_name}")


def build_skill_openai_tools(*, include_write: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    tools: List[Dict[str, Any]] = [SKILL_READ_TOOL, SKILL_GLOB_TOOL]
    registry = {
        "skill_read": "skill_read",
        "skill_glob": "skill_glob",
    }
    if include_write:
        tools.append(SKILL_WRITE_TOOL)
        registry["skill_write"] = "skill_write"
    return tools, registry
