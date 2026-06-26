# -*- coding: utf-8 -*-
"""request-scoped MCP Client：单次聊天/Skill 请求内复用连接。"""
from __future__ import annotations

import asyncio
import time
from contextlib import AsyncExitStack
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from fastmcp import Client

from backend.applications.agent.models.agent_model import McpServer
from backend.applications.base.rag.llm import OpenAICompatibleLLM
from backend.applications.mcp.adapters import format_resource_contents, format_tool_result
from backend.applications.mcp.audit import schedule_mcp_audit
from backend.applications.mcp.callbacks import build_tool_progress_handler, resolve_client_handlers
from backend.applications.mcp.cancel_scope import get_mcp_cancel_scope
from backend.applications.mcp.client_factory import open_client, resolve_timeout
from backend.applications.mcp.policies import McpAgentPolicy

_active_tool_step: ContextVar[Optional[dict]] = ContextVar("mcp_active_tool_step", default=None)


class McpSessionManager:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._clients: Dict[str, Client] = {}
        self._pending_process_events: List[Dict[str, Any]] = []
        self._policy = McpAgentPolicy()

    async def __aenter__(self) -> "McpSessionManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _on_process(self, event: Dict[str, Any]) -> None:
        self._pending_process_events.append(event)

    def drain_process_events(self) -> List[Dict[str, Any]]:
        events = self._pending_process_events
        self._pending_process_events = []
        return events

    async def open_servers(
            self,
            servers: List[McpServer],
            *,
            llm: Optional[OpenAICompatibleLLM] = None,
            policy: Optional[McpAgentPolicy] = None,
            llm_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._policy = policy or McpAgentPolicy()
        llm_kwargs = llm_kwargs or {}
        for server in servers:
            if server.id in self._clients:
                continue
            sampling_handler, log_handler = resolve_client_handlers(
                llm=llm,
                server=server,
                policy=self._policy,
                llm_kwargs=llm_kwargs,
                on_process=self._on_process,
                get_active_step=_active_tool_step.get,
            )
            self._clients[server.id] = await open_client(
                transport=server.transport,
                config=server.config,
                stack=self._stack,
                timeout=resolve_timeout(server.config),
                sampling_handler=sampling_handler,
                log_handler=log_handler,
            )

    async def call_tool(
            self,
            server: McpServer,
            tool_name: str,
            arguments: Optional[Dict[str, Any]] = None,
            *,
            step_dict: Optional[dict] = None,
    ) -> str:
        client = self._clients.get(server.id)
        if client is None:
            raise RuntimeError(f"MCP 服务「{server.name}」未建立会话，请先 open_servers")

        progress_handler = None
        if step_dict is not None and self._policy.log_mcp_progress:
            progress_handler = build_tool_progress_handler(
                server_name=server.name,
                step_dict=step_dict,
                on_process=self._on_process,
            )

        step_token = None
        if step_dict is not None:
            step_token = _active_tool_step.set(step_dict)

        started = time.perf_counter()
        args = arguments or {}

        def _audit(status: str, *, result_preview: str | None = None, error_message: str | None = None) -> None:
            schedule_mcp_audit(
                enabled=self._policy.audit_enabled,
                event_type="tool_call",
                mcp_server_id=server.id,
                server_name=server.name,
                transport=server.transport or "stdio",
                tool_name=tool_name,
                status=status,
                arguments=args,
                result_preview=result_preview,
                error_message=error_message,
                duration_ms=int((time.perf_counter() - started) * 1000),
                max_chars=self._policy.audit_max_chars,
            )

        try:
            call_task = asyncio.create_task(
                client.call_tool(
                    tool_name,
                    args,
                    progress_handler=progress_handler,
                )
            )
            cancel_scope = get_mcp_cancel_scope()
            while not call_task.done():
                if cancel_scope and cancel_scope.is_cancelled():
                    call_task.cancel()
                    try:
                        await call_task
                    except asyncio.CancelledError:
                        pass
                    if step_dict is not None:
                        step_dict["status"] = "cancelled"
                        step_dict["result"] = "已取消"
                    _audit("cancelled", error_message="用户取消")
                    raise asyncio.CancelledError("MCP tool call cancelled")
                await asyncio.wait({call_task}, timeout=0.05)

            result = await call_task
            text = format_tool_result(result)
            _audit("done", result_preview=text)
            return text
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _audit("error", error_message=str(exc))
            raise
        finally:
            if step_token is not None:
                _active_tool_step.reset(step_token)

    async def build_resource_context(
            self,
            servers: List[McpServer],
            *,
            max_chars: int,
            max_per_server: int,
    ) -> str:
        """读取 sync 缓存的 text resources 并拼接为 system 补充段（按字符上限截断）。"""
        blocks: list[str] = []
        remaining = max_chars

        for server in servers:
            if remaining <= 0:
                break
            client = self._clients.get(server.id)
            if client is None:
                continue
            resources = (server.config or {}).get("resources") or []
            for item in resources[:max_per_server]:
                if remaining <= 0:
                    break
                uri = item.get("uri")
                if not uri:
                    continue
                try:
                    text = format_resource_contents(await client.read_resource(uri)).strip()
                except Exception:
                    continue
                if not text:
                    continue
                if len(text) > remaining:
                    text = text[:remaining] + "…"
                label = item.get("name") or uri
                blocks.append(f"[{server.name}] {label}\n{text}")
                remaining -= len(text)

        if not blocks:
            return ""
        return "以下为 MCP Resources 内容（已自动注入）：\n\n" + "\n\n".join(blocks)

    async def close(self) -> None:
        await self._stack.aclose()
        self._clients.clear()
        self._pending_process_events.clear()
