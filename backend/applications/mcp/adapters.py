# -*- coding: utf-8 -*-
"""MCP 工具列表缓存、OpenAI function 适配、call_tool 结果格式化。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from mcp.types import AudioContent, EmbeddedResource, ImageContent, TextContent, Tool


def _tool_param_count(tool: Dict[str, Any]) -> int:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    return len((schema.get("properties") or {}))


def normalize_tools(raw_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in raw_tools or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or ""
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "description": item.get("description") or "",
                "param_count": item.get("param_count", _tool_param_count(item)),
                "input_schema": item.get("inputSchema") or item.get("input_schema") or {},
            }
        )
    return normalized


def tools_to_cache(tools: List[Tool]) -> List[Dict[str, Any]]:
    return normalize_tools(
        [tool.model_dump(by_alias=True, exclude_none=True) for tool in tools or []]
    )


def build_openai_tool_specs(
        mcp_servers: List[Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[Any, str]]]:
    """openai_name -> (mcp_server, original_tool_name)"""
    openai_tools: List[Dict[str, Any]] = []
    registry: Dict[str, Tuple[Any, str]] = {}
    used_names: set[str] = set()

    for server in mcp_servers:
        tools = normalize_tools((server.config or {}).get("tools") or [])
        prefix = (server.id or server.name or "mcp")[:8]
        for tool in tools:
            original_name = tool["name"]
            openai_name = original_name
            if openai_name in used_names:
                openai_name = f"{prefix}__{original_name}"
            used_names.add(openai_name)
            registry[openai_name] = (server, original_name)

            schema = tool.get("input_schema") or {}
            if not schema:
                schema = {"type": "object", "properties": {}}
            elif "type" not in schema:
                schema = {"type": "object", "properties": schema.get("properties") or {}}

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": openai_name,
                        "description": tool.get("description") or f"MCP 工具 {original_name}",
                        "parameters": schema,
                    },
                }
            )
    return openai_tools, registry


def build_mcp_metadata_block(mcp_servers: List[Any]) -> str:
    """将 sync 缓存的 instructions / prompts / resources 元信息格式化为 system 补充段。"""
    sections: list[str] = []
    for server in mcp_servers:
        config = server.config or {}
        instructions = (config.get("instructions") or "").strip()
        prompts = config.get("prompts") or []
        resources = config.get("resources") or []
        if not instructions and not prompts and not resources:
            continue

        lines = [f"### MCP 服务：{server.name}"]
        if instructions:
            lines.append(f"服务说明：{instructions}")
        if prompts:
            lines.append("可用 Prompts：")
            for item in prompts:
                name = item.get("name") or "未命名"
                desc = (item.get("description") or "").strip()
                lines.append(f"- {name}" + (f"：{desc}" if desc else ""))
        if resources:
            lines.append("可用 Resources：")
            for item in resources:
                uri = item.get("uri") or item.get("name") or "未命名"
                desc = (item.get("description") or item.get("name") or "").strip()
                lines.append(f"- {uri}" + (f"：{desc}" if desc else ""))
        sections.append("\n".join(lines))

    if not sections:
        return ""
    return (
        "以下为已绑定 MCP 服务的 Prompts / Resources 元信息（供参考，"
        "需要时可结合工具使用）：\n\n" + "\n\n".join(sections)
    )


def format_resource_contents(contents: Any) -> str:
    """FastMCP read_resource 返回 -> 可注入 LLM 的文本。"""
    if contents is None:
        return ""
    if isinstance(contents, str):
        return contents
    if not isinstance(contents, (list, tuple)):
        return str(contents)

    texts: list[str] = []
    for block in contents:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
        elif getattr(block, "blob", None) is not None:
            texts.append("[binary resource omitted]")
    return "\n".join(part for part in texts if part)


def format_tool_result(contents: Any) -> str:
    """FastMCP call_tool 返回 content 列表 -> LLM tool message 字符串。"""
    if contents is None:
        return ""
    if isinstance(contents, str):
        return contents
    if not isinstance(contents, (list, tuple)):
        try:
            return json.dumps(contents, ensure_ascii=False)
        except TypeError:
            return str(contents)

    texts: list[str] = []
    for block in contents:
        if isinstance(block, TextContent):
            texts.append(block.text or "")
        elif isinstance(block, ImageContent):
            texts.append(f"[image/{block.mimeType}]")
        elif isinstance(block, AudioContent):
            texts.append(f"[audio/{block.mimeType}]")
        elif isinstance(block, EmbeddedResource):
            resource = block.resource
            if getattr(resource, "text", None):
                texts.append(resource.text)
            else:
                texts.append("[embedded-resource]")
        else:
            texts.append(str(block))

    joined = "\n".join(part for part in texts if part)
    if joined:
        return joined
    try:
        return json.dumps(contents, ensure_ascii=False)
    except TypeError:
        return str(contents)
