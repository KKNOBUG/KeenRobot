# -*- coding: utf-8 -*-
"""MCP 流式请求取消：用户断开 SSE / AbortController 时中断 in-flight call_tool。"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import Optional


class McpCancelScope:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def request_cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


_cancel_scope: ContextVar[Optional[McpCancelScope]] = ContextVar("mcp_cancel_scope", default=None)


def bind_mcp_cancel_scope(scope: McpCancelScope) -> Token:
    return _cancel_scope.set(scope)


def reset_mcp_cancel_scope(token: Token) -> None:
    _cancel_scope.reset(token)


def get_mcp_cancel_scope() -> Optional[McpCancelScope]:
    return _cancel_scope.get()
