# -*- coding: utf-8 -*-
"""McpServer 配置 -> FastMCP Client；远程 list_tools / sync / diagnose。"""
from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from backend.applications.mcp_client.adapters import normalize_tools, tools_to_cache
from backend.applications.mcp_client.transports.streamable_http import ExactUrlStreamableHttpTransport
from backend.configure import LOGGER

SUPPORTED_TRANSPORTS = frozenset({"http", "sse", "stdio"})


def normalize_mcp_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """兼容前端扁平 command/args 与 config.stdio 两种 stdio 写法。"""
    config = dict(config or {})
    stdio_cfg = dict(config.get("stdio") or {})
    if not stdio_cfg.get("command") and config.get("command"):
        stdio_cfg = {
            "command": config.get("command"),
            "args": config.get("args") or [],
        }
        if config.get("env") is not None:
            stdio_cfg["env"] = config.get("env")
        if config.get("cwd"):
            stdio_cfg["cwd"] = config.get("cwd")
    if stdio_cfg.get("command"):
        config["stdio"] = stdio_cfg
    return config


def resolve_service_url(config: Optional[Dict[str, Any]]) -> Optional[str]:
    if not config:
        return None
    for key in ("url", "endpoint", "base_url", "service_url"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_timeout(config: Optional[Dict[str, Any]], default: float = 60.0) -> float:
    if not config:
        return default
    try:
        return float(config.get("timeout") or default)
    except (TypeError, ValueError):
        return default


def build_transport(transport: str, config: Optional[Dict[str, Any]]):
    transport = (transport or "stdio").lower()
    config = normalize_mcp_config(config)

    # http / sse 均走 Streamable HTTP POST（sse 为历史配置别名，非 GET SSETransport）
    if transport in {"http", "sse"}:
        url = resolve_service_url(config)
        if not url:
            raise ValueError("缺少服务地址，请填写服务地址")
        return ExactUrlStreamableHttpTransport(
            url=url,
            headers=dict(config.get("headers") or {}),
        )

    if transport == "stdio":
        stdio_cfg = config.get("stdio") or {}
        command = stdio_cfg.get("command")
        if not command:
            raise ValueError("stdio 传输缺少 config.stdio.command")
        return StdioTransport(
            command=command,
            args=stdio_cfg.get("args") or [],
            env=stdio_cfg.get("env"),
            cwd=stdio_cfg.get("cwd"),
        )

    raise ValueError(f"不支持的 transport: {transport}")


def _serialize_mcp_items(items: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in items or []:
        if hasattr(item, "model_dump"):
            row = item.model_dump(by_alias=True, exclude_none=True, mode="json")
        elif isinstance(item, dict):
            row = dict(item)
        else:
            continue
        if row.get("uri") is not None:
            row["uri"] = str(row["uri"])
        rows.append(row)
    return rows


async def open_client(
        *,
        transport: str,
        config: Optional[Dict[str, Any]],
        stack: AsyncExitStack,
        timeout: Optional[float] = None,
        sampling_handler=None,
        log_handler=None,
) -> Client:
    effective_timeout = timeout if timeout is not None else resolve_timeout(config)
    transport_obj = build_transport(transport, config)
    client_kwargs: Dict[str, Any] = {"timeout": effective_timeout}
    if sampling_handler is not None:
        client_kwargs["sampling_handler"] = sampling_handler
    if log_handler is not None:
        client_kwargs["log_handler"] = log_handler
    client = Client(transport_obj, **client_kwargs)
    await stack.enter_async_context(client)
    return client


async def _fetch_remote_lists(
        transport: str,
        config: Optional[Dict[str, Any]],
        *,
        include_resources: bool = True,
) -> Tuple[List[Any], List[Any], List[Any], Dict[str, Any]]:
    config = normalize_mcp_config(config)
    async with AsyncExitStack() as stack:
        client = await open_client(transport=transport, config=config, stack=stack)
        tools = await client.list_tools()
        resources: List[Any] = []
        prompts: List[Any] = []
        if include_resources:
            try:
                resources = await client.list_resources()
            except Exception as exc:
                if "Method not found" not in str(exc):
                    raise
            try:
                prompts = await client.list_prompts()
            except Exception as exc:
                if "Method not found" not in str(exc):
                    raise
        init_data: Dict[str, Any] = {}
        if client.initialize_result is not None and hasattr(client.initialize_result, "model_dump"):
            init_data = client.initialize_result.model_dump(
                by_alias=True, exclude_none=True, mode="json",
            )
    return tools, resources, prompts, init_data


async def list_remote_tools(transport: str, config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    transport = (transport or "stdio").lower()
    config = normalize_mcp_config(config)
    if transport not in SUPPORTED_TRANSPORTS:
        return normalize_tools(config.get("tools") or [])

    if transport == "stdio" and not (config.get("stdio") or {}).get("command"):
        return normalize_tools(config.get("tools") or [])

    try:
        tools, _, _, _ = await _fetch_remote_lists(transport, config, include_resources=False)
        return tools_to_cache(tools)
    except Exception as exc:
        LOGGER.warning(f"刷新 MCP 工具列表失败: {exc}")
        raise


async def sync_remote_server(
        transport: str,
        config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """拉取 tools / resources / prompts / capabilities 并返回可写入 DB 的缓存块。"""
    transport = (transport or "stdio").lower()
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"不支持的 transport: {transport}")

    tools, resources, prompts, init_data = await _fetch_remote_lists(transport, config)
    return {
        "tools": tools_to_cache(tools),
        "resources": _serialize_mcp_items(resources),
        "prompts": _serialize_mcp_items(prompts),
        "capabilities": init_data.get("capabilities") or {},
        "server_info": init_data.get("serverInfo") or init_data.get("server_info") or {},
        "instructions": init_data.get("instructions") or "",
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


async def diagnose_connection(
        transport: str,
        config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """连接诊断：initialize + list_tools + list_resources，不写 DB。"""
    transport = (transport or "stdio").lower()
    if transport not in SUPPORTED_TRANSPORTS:
        return {"ok": False, "transport": transport, "error": f"不支持的 transport: {transport}"}

    try:
        tools, resources, prompts, init_data = await _fetch_remote_lists(transport, config)
        return {
            "ok": True,
            "transport": transport,
            "tool_count": len(tools or []),
            "resource_count": len(resources or []),
            "prompt_count": len(prompts or []),
            "capabilities": init_data.get("capabilities") or {},
            "server_info": init_data.get("serverInfo") or init_data.get("server_info") or {},
            "protocol_version": init_data.get("protocolVersion") or init_data.get("protocol_version"),
        }
    except Exception as exc:
        LOGGER.warning(f"MCP 连接诊断失败: {exc}")
        return {"ok": False, "transport": transport, "error": str(exc)}
