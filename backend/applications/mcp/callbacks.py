# -*- coding: utf-8 -*-
"""MCP Client 回调：progress / log / sampling → process_trace 与 LOGGER；elicitation 待 SDK。"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from mcp.types import LoggingMessageNotificationParams, SamplingMessage, TextContent

from backend.applications.agent.models.agent_model import McpServer
from backend.applications.base.rag.llm import OpenAICompatibleLLM
from backend.applications.mcp.audit import schedule_mcp_audit
from backend.applications.mcp.policies import McpAgentPolicy
from backend.configure import LOGGER

ProcessEventSink = Callable[[Dict[str, Any]], Any]

_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "alert": logging.CRITICAL,
    "emergency": logging.CRITICAL,
}


def format_progress_line(progress: float, total: float | None, message: str | None) -> str:
    if total is not None and total > 0:
        percent = (progress / total) * 100
        line = f"{progress:g}/{total:g} ({percent:.1f}%)"
    else:
        line = f"{progress:g}"
    if message:
        return f"{line} — {message}"
    return line


def _format_log_line(params: LoggingMessageNotificationParams) -> str:
    data = (params.data or "").strip()
    if params.logger:
        return f"{params.logger}: {data}" if data else params.logger
    return data or "(empty log message)"


def _sampling_content_to_text(content: Any) -> str:
    if isinstance(content, TextContent):
        return content.text or ""
    mime = getattr(content, "mimeType", None) or getattr(content, "type", "unknown")
    return f"[{mime} content omitted]"


def _sampling_messages_to_openai(
        messages: List[SamplingMessage],
        *,
        system_prompt: Optional[str],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if system_prompt:
        rows.append({"role": "system", "content": system_prompt})
    for message in messages:
        rows.append(
            {
                "role": message.role,
                "content": _sampling_content_to_text(message.content),
            }
        )
    return rows


async def _emit_process(sink: Optional[ProcessEventSink], event: Dict[str, Any]) -> None:
    if sink is None:
        return
    result = sink(event)
    if inspect.isawaitable(result):
        await result


def _append_step_log(step_dict: dict, line: str) -> None:
    logs = step_dict.setdefault("logs", [])
    if not logs or logs[-1] != line:
        logs.append(line)


def build_tool_progress_handler(
        *,
        server_name: str,
        step_dict: dict,
        on_process: Optional[ProcessEventSink] = None,
):
    """单次 call_tool 的 progress 回调（支持并行 tool_calls 各自绑定 step）。"""

    async def handler(progress: float, total: float | None, message: str | None) -> None:
        line = format_progress_line(progress, total, message)
        LOGGER.info("MCP progress [%s] %s", server_name, line)
        _append_step_log(step_dict, line)
        await _emit_process(on_process, {"type": "process", "step": dict(step_dict)})

    return handler


def build_log_handler(
        *,
        server_name: str,
        policy: McpAgentPolicy,
        on_process: Optional[ProcessEventSink] = None,
        get_active_step: Callable[[], Optional[dict]],
):
    """MCP Server notifications/message 日志；执行工具期间写入当前 step.logs。"""

    async def handler(params: LoggingMessageNotificationParams) -> None:
        if not policy.log_mcp_progress:
            return
        line = _format_log_line(params)
        level = _LOG_LEVELS.get((params.level or "info").lower(), logging.INFO)
        LOGGER.log(level, "MCP log [%s] %s", server_name, line)
        step = get_active_step()
        if step is not None:
            _append_step_log(step, line)
            await _emit_process(on_process, {"type": "process", "step": dict(step)})

    return handler


def build_sampling_handler(
        *,
        llm: OpenAICompatibleLLM,
        server: McpServer,
        policy: McpAgentPolicy,
        llm_kwargs: Dict[str, Any],
        on_process: Optional[ProcessEventSink] = None,
):
    """MCP Server 发起 sampling/createMessage 时，转发到当前会话 LLM。"""
    server_name = server.name

    async def handler(messages, params, _context):
        import time

        started = time.perf_counter()
        openai_messages = _sampling_messages_to_openai(
            messages,
            system_prompt=params.systemPrompt,
        )
        step = {
            "type": "mcp",
            "server": server_name,
            "tool": "sampling/createMessage",
            "arguments": {"messages": len(messages)},
            "status": "running",
        }
        await _emit_process(on_process, {"type": "process", "step": dict(step)})

        temperature = (
            params.temperature
            if params.temperature is not None
            else llm_kwargs.get("temperature", 0.7)
        )
        max_tokens = (
            params.maxTokens
            if params.maxTokens is not None
            else llm_kwargs.get("max_tokens", 2048)
        )

        def _audit(status: str, *, preview: str | None = None, error: str | None = None) -> None:
            schedule_mcp_audit(
                enabled=policy.audit_enabled,
                event_type="sampling",
                mcp_server_id=server.id,
                server_name=server_name,
                transport=server.transport or "stdio",
                tool_name="sampling/createMessage",
                status=status,
                arguments={"messages": len(messages)},
                result_preview=preview,
                error_message=error,
                duration_ms=int((time.perf_counter() - started) * 1000),
                max_chars=policy.audit_max_chars,
            )

        try:
            text = await asyncio.to_thread(
                llm.chat,
                openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=llm_kwargs.get("top_p", 0.95),
                enable_thinking=llm_kwargs.get("enable_thinking", False),
            )
            step["status"] = "done"
            preview = (text or "").strip()
            if len(preview) > 500:
                preview = preview[:500] + "…"
            step["result"] = preview
            await _emit_process(on_process, {"type": "process", "step": dict(step)})
            _audit("done", preview=preview)
            return text
        except Exception as exc:
            LOGGER.warning(f"MCP sampling 失败 [{server_name}]: {exc}")
            step["status"] = "error"
            step["result"] = str(exc)
            await _emit_process(on_process, {"type": "process", "step": dict(step)})
            _audit("error", error=str(exc))
            raise

    return handler


def build_elicitation_reject_handler(reason: str = "MCP elicitation 未启用（待 SDK 支持）"):
    """MCP SDK 尚无 ElicitRequest；占位拒绝 handler。"""

    def handler(_request, _context):
        raise RuntimeError(reason)

    return handler


def resolve_client_handlers(
        *,
        llm: Optional[OpenAICompatibleLLM],
        server: McpServer,
        policy: McpAgentPolicy,
        llm_kwargs: Optional[Dict[str, Any]] = None,
        on_process: Optional[ProcessEventSink] = None,
        get_active_step: Callable[[], Optional[dict]],
) -> tuple[Any, Any]:
    """返回 (sampling_handler, log_handler)。"""
    if policy.sampling_mode != "llm" or llm is None:

        def reject_handler(_messages, _params, _context):
            raise RuntimeError("MCP sampling 未启用")

        sampling_handler = reject_handler
    else:
        sampling_handler = build_sampling_handler(
            llm=llm,
            server=server,
            policy=policy,
            llm_kwargs=llm_kwargs or {},
            on_process=on_process,
        )

    log_handler = build_log_handler(
        server_name=server.name,
        policy=policy,
        on_process=on_process,
        get_active_step=get_active_step,
    )
    return sampling_handler, log_handler
