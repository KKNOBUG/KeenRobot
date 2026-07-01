# -*- coding: utf-8 -*-
"""
Streamable HTTP transport that preserves the configured URL exactly.

FastMCP 默认会在 path 末尾追加 `/`，部分 MCP 服务（如 mcpmarket.cn）
在该 URL 下返回 404，initialize 失败并报 `Session terminated`。
"""
from __future__ import annotations

import contextlib
import datetime
from collections.abc import AsyncIterator
from typing import Any, Callable, Literal, Unpack, Dict

import httpx
from mcp import ClientSession
from pydantic import AnyUrl

from fastmcp.client.transports import ClientTransport, SessionKwargs
from fastmcp.server.dependencies import get_http_headers


class ExactUrlStreamableHttpTransport(ClientTransport):
    """与 FastMCP StreamableHttpTransport 相同，但不修改 URL path。"""

    def __init__(
            self,
            url: str | AnyUrl,
            headers: dict[str, str] | None = None,
            auth: httpx.Auth | Literal["oauth"] | str | None = None,
            sse_read_timeout: datetime.timedelta | float | int | None = None,
            httpx_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ):
        if isinstance(url, AnyUrl):
            url = str(url)
        if not isinstance(url, str) or not url.startswith("http"):
            raise ValueError("Invalid HTTP/S URL provided for Streamable HTTP.")

        self.url = url.strip()
        self.headers = headers or {}
        self.auth = auth
        self.httpx_client_factory = httpx_client_factory

        if isinstance(sse_read_timeout, int | float):
            sse_read_timeout = datetime.timedelta(seconds=sse_read_timeout)
        self.sse_read_timeout = sse_read_timeout

    @contextlib.asynccontextmanager
    async def connect_session(
            self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]:
        from mcp.client.streamable_http import streamablehttp_client

        client_kwargs: Dict[str, Any] = {"headers": get_http_headers() | self.headers}

        if self.sse_read_timeout is not None:
            client_kwargs["sse_read_timeout"] = self.sse_read_timeout
        if session_kwargs.get("read_timeout_seconds", None) is not None:
            client_kwargs["timeout"] = session_kwargs.get("read_timeout_seconds")

        if self.httpx_client_factory is not None:
            client_kwargs["httpx_client_factory"] = self.httpx_client_factory

        async with streamablehttp_client(
                self.url,
                auth=self.auth,
                **client_kwargs,
        ) as transport:
            read_stream, write_stream, _ = transport
            async with ClientSession(
                    read_stream, write_stream, **session_kwargs
            ) as session:
                yield session

    def __repr__(self) -> str:
        return f"<ExactUrlStreamableHttpTransport(url='{self.url}')>"
