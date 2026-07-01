# -*- coding: utf-8 -*-
"""MCP 业务审计：异步落库 + 参数脱敏。"""
from __future__ import annotations

import asyncio
import json
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.common.request_context import get_trace_id
from backend.configure import LOGGER

_SENSITIVE_KEY = re.compile(r"(password|token|api[_-]?key|secret|authorization)", re.I)
_DEFAULT_MAX_CHARS = 4096


@dataclass
class McpAuditContext:
    user_id: int
    username: str
    conversation_id: Optional[str] = None
    skill_id: Optional[str] = None
    skill_run_id: Optional[str] = None


_audit_ctx: ContextVar[Optional[McpAuditContext]] = ContextVar("mcp_audit_ctx", default=None)


def bind_mcp_audit_context(ctx: McpAuditContext) -> Token:
    return _audit_ctx.set(ctx)


def reset_mcp_audit_context(token: Token) -> None:
    _audit_ctx.reset(token)


def get_mcp_audit_context() -> Optional[McpAuditContext]:
    return _audit_ctx.get()


def redact_json_value(value: Any, *, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for key, item in obj.items():
                if _SENSITIVE_KEY.search(str(key)):
                    out[key] = "***"
                else:
                    out[key] = _walk(item)
            return out
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    try:
        text = json.dumps(_walk(value), ensure_ascii=False)
    except TypeError:
        text = str(value)
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


def schedule_mcp_audit(
        *,
        enabled: bool,
        event_type: str,
        mcp_server_id: str,
        server_name: str,
        transport: str,
        tool_name: str,
        status: str,
        arguments: Optional[dict] = None,
        result_preview: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        max_chars: int = _DEFAULT_MAX_CHARS,
) -> None:
    if not enabled:
        return
    ctx = get_mcp_audit_context()
    if ctx is None:
        return
    payload = {
        "user_id": ctx.user_id,
        "username": ctx.username,
        "conversation_id": ctx.conversation_id,
        "skill_id": ctx.skill_id,
        "skill_run_id": ctx.skill_run_id,
        "mcp_server_id": mcp_server_id,
        "server_name": server_name,
        "transport": transport,
        "event_type": event_type,
        "tool_name": tool_name,
        "status": status,
        "arguments_json": redact_json_value(arguments, max_chars=max_chars) if arguments else None,
        "result_preview": (result_preview or "")[:max_chars] or None,
        "error_message": (error_message or "")[:512] or None,
        "duration_ms": duration_ms,
        "trace_id": get_trace_id() or None,
    }

    async def _write() -> None:
        try:
            from backend.applications.agent.models.mcp_audit_model import McpAuditLog

            await McpAuditLog.create(**payload)
        except Exception as exc:
            LOGGER.warning("MCP 审计落库失败: %s", exc)

    asyncio.create_task(_write())
