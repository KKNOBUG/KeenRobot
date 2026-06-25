# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : mcp_agent.py
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.applications.agent.models.agent_model import McpServer
from backend.applications.agent.services.agent_crud import McpServerCrud
from backend.applications.agent.services.mcp_tools import (
    build_openai_tool_specs,
    call_remote_tool,
)
from backend.applications.base.rag.chain import _resolve_system_prompt, _retrieve_context
from backend.applications.base.rag.llm import OpenAICompatibleLLM, format_messages, merge_token_usage
from backend.applications.conversation.schemas.process_step_schema import McpStep
from backend.applications.user.models.user_model import User

MAX_MCP_TOOL_ROUNDS = 6

MCP_AGENT_SYSTEM_PROMPT = """你是一个可以调用外部 MCP 工具的智能助手。

规则：
1. 当用户问题需要地图、天气、实时数据等外部能力时，优先调用已提供的工具。
2. 工具返回结果后，用自然语言整理并回答用户。
3. 若无需工具即可回答，直接回复，不要强行调用工具。
4. 结合参考资料（若有）与工具结果给出准确、简洁的中文回答。
"""


async def _load_mcp_servers(mcp_ids: List[str], user: User) -> List[McpServer]:
    crud = McpServerCrud()
    servers: List[McpServer] = []
    for mcp_id in mcp_ids:
        server = await crud.get_mcp_server(mcp_id, user)
        if not server.is_enabled:
            continue
        tools = (server.config or {}).get("tools") or []
        if not tools:
            raise ValueError(f"MCP 服务「{server.name}」尚未刷新工具列表，请先在 MCP 管理中点击「刷新」")
        servers.append(server)
    return servers


async def mcp_agent_stream(
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]],
        mcp_ids: List[str],
        user: User,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        system_prompt: str = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        max_history_rounds: int = 10,
        enable_thinking: bool = False,
) -> AsyncIterator[Dict[str, Any]]:
    """带 MCP 工具调用的 Agent 流式问答。"""
    mcp_servers = await _load_mcp_servers(mcp_ids, user)
    openai_tools, tool_registry = build_openai_tool_specs(mcp_servers)
    if not openai_tools:
        raise ValueError("所选 MCP 服务没有可用工具，请先在管理页刷新工具列表")

    search_results, context = _retrieve_context(
        question,
        knowledge_base_ids,
        top_k=top_k,
        score_threshold=score_threshold,
    )
    has_context = bool(search_results) and bool(context.strip())

    rag_prompt = _resolve_system_prompt(
        system_prompt=system_prompt,
        context=context if has_context else "（无特定参考资料）",
        has_context=has_context,
    )
    combined_system = f"{MCP_AGENT_SYSTEM_PROMPT}\n\n{rag_prompt}"

    messages = format_messages(
        system_prompt=combined_system,
        user_question=question,
        context=context,
        chat_history=chat_history,
        max_history_rounds=max_history_rounds,
        format_context=False,
    )

    llm = OpenAICompatibleLLM(model=model_name, api_key=api_key, base_url=base_url)
    process_trace: List[dict] = []
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}

    for _round in range(MAX_MCP_TOOL_ROUNDS):
        completion = await llm.chat_with_tools(
            messages=messages,
            tools=openai_tools,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            enable_thinking=enable_thinking,
        )
        merge_token_usage(usage_acc, completion.get("usage"))

        tool_calls = completion.get("tool_calls") or []
        if tool_calls:
            assistant_message = {
                "role": "assistant",
                "content": completion.get("content") or "",
                "tool_calls": tool_calls,
            }
            messages.append(assistant_message)

            for tool_call in tool_calls:
                func = tool_call.get("function") or {}
                openai_name = func.get("name") or ""
                raw_args = func.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}

                server, original_tool_name = tool_registry.get(openai_name, (None, openai_name))
                server_name = server.name if server else "MCP"
                step = McpStep(
                    server=server_name,
                    tool=original_tool_name,
                    arguments=arguments,
                    status="running",
                )
                step_dict = step.model_dump()
                process_trace.append(step_dict)
                yield {"type": "process", "step": step_dict}

                try:
                    if not server:
                        raise ValueError(f"未找到工具映射: {openai_name}")
                    result_text = await call_remote_tool(
                        server.transport,
                        server.config,
                        original_tool_name,
                        arguments,
                    )
                    step_dict["status"] = "done"
                    step_dict["result"] = result_text
                except Exception as exc:
                    step_dict["status"] = "error"
                    step_dict["result"] = str(exc)

                yield {"type": "process", "step": dict(step_dict)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": step_dict.get("result") or "",
                    }
                )
            continue

        final_content = (completion.get("content") or "").strip()
        if final_content:
            chunk_size = 8
            for i in range(0, len(final_content), chunk_size):
                yield {"type": "content", "content": final_content[i:i + chunk_size]}
                await asyncio.sleep(0.01)
        else:
            async for chunk in llm.stream_chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    enable_thinking=enable_thinking,
            ):
                if chunk.get("type") == "usage":
                    merge_token_usage(usage_acc, chunk)
                    continue
                yield chunk

        yield {"type": "process_trace", "process_trace": process_trace}
        if any(usage_acc.values()):
            yield {"type": "usage", **usage_acc}
        return

    raise RuntimeError(f"MCP 工具调用超过最大轮次 {MAX_MCP_TOOL_ROUNDS}")
