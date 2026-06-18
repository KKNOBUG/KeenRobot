# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : mcp_tools.py
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.configure import LOGGER


def _tool_param_count(tool: Dict[str, Any]) -> int:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    props = schema.get("properties") or {}
    return len(props)


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


def _resolve_service_url(config: Optional[Dict[str, Any]]) -> Optional[str]:
    if not config:
        return None
    for key in ("url", "endpoint", "base_url", "service_url"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _format_tool_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        return str(result)


MCP_HTTP_ACCEPT = "application/json, text/event-stream"


def _default_mcp_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    merged = dict(headers or {})
    merged["Accept"] = MCP_HTTP_ACCEPT
    merged.setdefault("Content-Type", "application/json")
    return merged


def _parse_sse_body(text: str) -> Dict[str, Any]:
    """解析 MCP Streamable HTTP 的 SSE 响应体。"""
    messages: List[Dict[str, Any]] = []
    for block in text.split("\n\n"):
        data_line = None
        for line in block.splitlines():
            if line.startswith("data:"):
                data_line = line[5:].strip()
        if not data_line:
            continue
        try:
            parsed = json.loads(data_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            messages.append(parsed)

    for msg in reversed(messages):
        if msg.get("result") is not None or msg.get("error") is not None:
            return msg
    return messages[-1] if messages else {}


def _parse_mcp_http_response(response: httpx.Response) -> Dict[str, Any]:
    content_type = (response.headers.get("content-type") or "").lower()
    text = (response.text or "").strip()

    if response.status_code in {202, 204} and not text:
        return {}

    if "text/event-stream" in content_type or text.startswith("event:"):
        return _parse_sse_body(text)

    if not text:
        return {}

    body = response.json()
    return body if isinstance(body, dict) else {}


class McpHttpClient:
    """Streamable HTTP MCP 会话：initialize 后复用 session 调用 tools/list、tools/call。"""

    def __init__(
            self,
            url: str,
            headers: Optional[Dict[str, str]] = None,
            timeout: float = 60,
    ):
        self.url = url
        self.base_headers = _default_mcp_headers(headers)
        self.timeout = timeout
        self.session_headers: Dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def __aenter__(self) -> "McpHttpClient":
        self._client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _rpc(
            self,
            method: str,
            params: Optional[Dict[str, Any]] = None,
            *,
            is_notification: bool = False,
    ) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("MCP 客户端未初始化")

        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        if not is_notification:
            payload["id"] = self._next_id()

        response = await self._client.post(
            self.url,
            json=payload,
            headers=self.session_headers,
        )
        if is_notification and response.status_code in {200, 202, 204}:
            return {}

        response.raise_for_status()
        body = _parse_mcp_http_response(response)
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(body["error"].get("message") or str(body["error"]))
        return body if isinstance(body, dict) else {}

    async def _initialize(self) -> None:
        init_resp = await self._client.post(
            self.url,
            json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "KeenRobot", "version": "1.0.0"},
                },
            },
            headers=self.base_headers,
        )
        init_resp.raise_for_status()
        init_body = _parse_mcp_http_response(init_resp)
        if init_body.get("error"):
            raise RuntimeError(init_body["error"].get("message") or str(init_body["error"]))

        self.session_headers = dict(self.base_headers)
        session_id = init_resp.headers.get("mcp-session-id") or init_resp.headers.get("Mcp-Session-Id")
        if session_id:
            self.session_headers["Mcp-Session-Id"] = session_id

        await self._rpc("notifications/initialized", {}, is_notification=True)

    async def list_tools(self) -> List[Dict[str, Any]]:
        body = await self._rpc("tools/list", {})
        raw_tools = (body.get("result") or {}).get("tools") or []
        return normalize_tools(raw_tools)

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        body = await self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        result = body.get("result") or {}
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text") or "")
                if texts:
                    return "\n".join(texts)
            if "structuredContent" in result:
                return _format_tool_result(result["structuredContent"])
        return _format_tool_result(result)


async def fetch_remote_tools(transport: str, config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从远程 MCP 服务拉取工具列表。"""
    transport = (transport or "stdio").lower()
    if transport not in {"http", "sse"}:
        return normalize_tools((config or {}).get("tools") or [])

    url = _resolve_service_url(config)
    if not url:
        raise ValueError("缺少服务地址，请填写服务地址")

    request_headers = dict((config or {}).get("headers") or {})
    timeout = float((config or {}).get("timeout") or 30)

    async with McpHttpClient(url=url, headers=request_headers, timeout=timeout) as client:
        return await client.list_tools()


async def call_remote_tool(
        transport: str,
        config: Optional[Dict[str, Any]],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
) -> str:
    transport = (transport or "stdio").lower()
    if transport not in {"http", "sse"}:
        raise ValueError("当前仅支持 HTTP/SSE 类型 MCP 在聊天中调用工具")

    url = _resolve_service_url(config)
    if not url:
        raise ValueError("MCP 服务缺少 url 配置")

    request_headers = dict((config or {}).get("headers") or {})
    timeout = float((config or {}).get("timeout") or 60)

    async with McpHttpClient(url=url, headers=request_headers, timeout=timeout) as client:
        return await client.call_tool(tool_name, arguments)


async def refresh_mcp_tools(transport: str, config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        return await fetch_remote_tools(transport, config)
    except Exception as exc:
        LOGGER.warning(f"刷新 MCP 工具列表失败: {exc}")
        raise


def build_openai_tool_specs(
        mcp_servers: List[Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[Any, str]]]:
    """
    将多个 MCP 服务的工具转为 OpenAI function tools，并返回名称映射表。

    openai_name -> (mcp_server_instance, original_tool_name)
    """
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
