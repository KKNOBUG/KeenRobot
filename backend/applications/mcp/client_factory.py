# -*- coding: utf-8 -*-
"""McpServer 配置 -> FastMCP Client；远程 list_tools。"""
from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from backend.applications.mcp.adapters import normalize_tools, tools_to_cache
from backend.applications.mcp.transports.streamable_http import ExactUrlStreamableHttpTransport
from backend.configure import LOGGER


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
    config = config or {}

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


async def open_client(
        *,
        transport: str,
        config: Optional[Dict[str, Any]],
        stack: AsyncExitStack,
        timeout: Optional[float] = None,
) -> Client:
    effective_timeout = timeout if timeout is not None else resolve_timeout(config)
    transport_obj = build_transport(transport, config)
    client = Client(transport_obj, timeout=effective_timeout)
    await stack.enter_async_context(client)
    return client


async def list_remote_tools(transport: str, config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    transport = (transport or "stdio").lower()
    if transport not in {"http", "sse", "stdio"}:
        return normalize_tools((config or {}).get("tools") or [])

    if transport == "stdio":
        stdio_cfg = (config or {}).get("stdio") or {}
        if not stdio_cfg.get("command"):
            return normalize_tools((config or {}).get("tools") or [])

    try:
        async with AsyncExitStack() as stack:
            client = await open_client(transport=transport, config=config, stack=stack)
            return tools_to_cache(await client.list_tools())
    except Exception as exc:
        LOGGER.warning(f"刷新 MCP 工具列表失败: {exc}")
        raise
