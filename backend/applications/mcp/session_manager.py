# -*- coding: utf-8 -*-
"""request-scoped MCP Client：单次聊天/Skill 请求内复用连接。"""
from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from fastmcp import Client

from backend.applications.agent.models.agent_model import McpServer
from backend.applications.mcp.adapters import format_tool_result
from backend.applications.mcp.client_factory import open_client, resolve_timeout


class McpSessionManager:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._clients: Dict[str, Client] = {}

    async def __aenter__(self) -> "McpSessionManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def open_servers(self, servers: List[McpServer]) -> None:
        for server in servers:
            if server.id in self._clients:
                continue
            self._clients[server.id] = await open_client(
                transport=server.transport,
                config=server.config,
                stack=self._stack,
                timeout=resolve_timeout(server.config),
            )

    async def call_tool(
            self,
            server: McpServer,
            tool_name: str,
            arguments: Optional[Dict[str, Any]] = None,
    ) -> str:
        client = self._clients.get(server.id)
        if client is None:
            raise RuntimeError(f"MCP 服务「{server.name}」未建立会话，请先 open_servers")
        result = await client.call_tool(tool_name, arguments or {})
        return format_tool_result(result)

    async def close(self) -> None:
        await self._stack.aclose()
        self._clients.clear()
