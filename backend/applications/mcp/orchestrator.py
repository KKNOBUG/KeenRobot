# -*- coding: utf-8 -*-
"""MCP Agent ReAct 编排：RAG + LLM tools + SessionManager + SSE。"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from backend.applications.agent.models.agent_model import McpServer
from backend.applications.agent.services.agent_crud import McpServerCrud
from backend.applications.base.rag.chain import _resolve_system_prompt, _retrieve_context
from backend.applications.base.rag.llm import OpenAICompatibleLLM, format_messages, merge_token_usage
from backend.applications.conversation.schemas.process_step_schema import McpStep
from backend.applications.mcp.adapters import build_mcp_metadata_block, build_openai_tool_specs
from backend.applications.mcp.audit import McpAuditContext, bind_mcp_audit_context, reset_mcp_audit_context
from backend.applications.mcp.cancel_scope import McpCancelScope, bind_mcp_cancel_scope, get_mcp_cancel_scope, reset_mcp_cancel_scope
from backend.applications.mcp.policies import McpAgentPolicy
from backend.applications.mcp.session_manager import McpSessionManager
from backend.applications.user.models.user_model import User

MCP_AGENT_SYSTEM_PROMPT = """你是一个可以调用外部 MCP 工具的智能助手。

规则：
1. 当用户问题需要地图、天气、实时数据等外部能力时，优先调用已提供的工具。
2. 工具返回结果后，用自然语言整理并回答用户。
3. 若无需工具即可回答，直接回复，不要强行调用工具。
4. 结合参考资料（若有）与工具结果给出准确、简洁的中文回答。
"""


async def load_mcp_servers(mcp_ids: List[str], user: User) -> List[McpServer]:
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


class McpAgentOrchestrator:
    async def stream(
            self,
            *,
            question: str,
            mcp_server_ids: List[str],
            user: User,
            knowledge_base_ids: Optional[List[str]] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
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
            mcp_system_prompt: str = MCP_AGENT_SYSTEM_PROMPT,
            policy: Optional[McpAgentPolicy] = None,
            conversation_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        policy = policy or McpAgentPolicy()
        audit_token = bind_mcp_audit_context(
            McpAuditContext(
                user_id=user.id,
                username=getattr(user, "username", None) or str(user.id),
                conversation_id=conversation_id,
            )
        )
        cancel_scope = McpCancelScope()
        cancel_token = bind_mcp_cancel_scope(cancel_scope)
        try:
            async for event in self._stream_impl(
                    question=question,
                    mcp_server_ids=mcp_server_ids,
                    user=user,
                    knowledge_base_ids=knowledge_base_ids,
                    chat_history=chat_history,
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    system_prompt=system_prompt,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    max_history_rounds=max_history_rounds,
                    enable_thinking=enable_thinking,
                    mcp_system_prompt=mcp_system_prompt,
                    policy=policy,
            ):
                yield event
        except asyncio.CancelledError:
            cancel_scope.request_cancel()
            raise
        finally:
            reset_mcp_cancel_scope(cancel_token)
            reset_mcp_audit_context(audit_token)

    async def _stream_impl(
            self,
            *,
            question: str,
            mcp_server_ids: List[str],
            user: User,
            knowledge_base_ids: Optional[List[str]] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
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
            mcp_system_prompt: str = MCP_AGENT_SYSTEM_PROMPT,
            policy: McpAgentPolicy,
    ) -> AsyncIterator[Dict[str, Any]]:
        mcp_servers = await load_mcp_servers(mcp_server_ids, user)
        openai_tools, tool_registry = build_openai_tool_specs(mcp_servers)
        if not openai_tools:
            raise ValueError("所选 MCP 服务没有可用工具，请先在管理页刷新工具列表")

        search_results, context = _retrieve_context(
            question,
            knowledge_base_ids or [],
            top_k=top_k,
            score_threshold=score_threshold,
        )
        has_context = bool(search_results) and bool(context.strip())
        rag_prompt = _resolve_system_prompt(
            system_prompt=system_prompt,
            context=context if has_context else "（无特定参考资料）",
            has_context=has_context,
        )
        mcp_metadata = build_mcp_metadata_block(mcp_servers)
        system_parts = [mcp_system_prompt, rag_prompt]
        if mcp_metadata:
            system_parts.append(mcp_metadata)
        messages = format_messages(
            system_prompt="\n\n".join(system_parts),
            user_question=question,
            context=context,
            chat_history=chat_history or [],
            max_history_rounds=max_history_rounds,
            format_context=False,
        )

        llm = OpenAICompatibleLLM(model=model_name, api_key=api_key, base_url=base_url)
        process_trace: List[dict] = []
        usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}
        llm_kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "enable_thinking": enable_thinking,
        }

        async with McpSessionManager() as mcp_session:
            await mcp_session.open_servers(
                mcp_servers,
                llm=llm,
                policy=policy,
                llm_kwargs=llm_kwargs,
            )
            if policy.inject_resource_contents and messages and messages[0].get("role") == "system":
                resource_ctx = await mcp_session.build_resource_context(
                    mcp_servers,
                    max_chars=policy.max_injected_resource_chars,
                    max_per_server=policy.max_resources_per_server,
                )
                if resource_ctx:
                    messages[0]["content"] = f"{messages[0]['content']}\n\n{resource_ctx}"

            for _round in range(policy.max_tool_rounds):
                if get_mcp_cancel_scope() and get_mcp_cancel_scope().is_cancelled():
                    raise asyncio.CancelledError("MCP chat cancelled")
                completion = await llm.chat_with_tools(
                    messages=messages,
                    tools=openai_tools,
                    **llm_kwargs,
                )
                merge_token_usage(usage_acc, completion.get("usage"))

                tool_calls = completion.get("tool_calls") or []
                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": completion.get("content") or "",
                            "tool_calls": tool_calls,
                        }
                    )
                    async for event in self._dispatch_tool_calls(
                            tool_calls,
                            tool_registry,
                            mcp_session,
                            messages,
                            process_trace,
                            parallel=policy.parallel_tool_calls and len(tool_calls) > 1,
                    ):
                        yield event
                    continue

                async for event in self._stream_final_answer(
                        llm=llm,
                        messages=messages,
                        completion=completion,
                        process_trace=process_trace,
                        usage_acc=usage_acc,
                        llm_kwargs=llm_kwargs,
                ):
                    yield event
                return

            if policy.on_max_rounds == "summarize":
                messages.append(
                    {
                        "role": "user",
                        "content": "工具调用轮次已达上限，请根据已有工具结果简要总结并回答用户。",
                    }
                )
                async for event in self._stream_final_answer(
                        llm=llm,
                        messages=messages,
                        completion={"content": ""},
                        process_trace=process_trace,
                        usage_acc=usage_acc,
                        llm_kwargs=llm_kwargs,
                ):
                    yield event
                return

        raise RuntimeError(f"MCP 工具调用超过最大轮次 {policy.max_tool_rounds}")

    async def _dispatch_tool_calls(
            self,
            tool_calls: List[dict],
            tool_registry: Dict[str, tuple],
            mcp_session: McpSessionManager,
            messages: List[dict],
            process_trace: List[dict],
            *,
            parallel: bool,
    ) -> AsyncIterator[Dict[str, Any]]:
        pending: List[Tuple[dict, dict]] = []
        for tool_call in tool_calls:
            step_dict = self._build_running_step(tool_call, tool_registry)
            process_trace.append(step_dict)
            yield {"type": "process", "step": step_dict}
            pending.append((tool_call, step_dict))

        async def run_one(tool_call: dict, step_dict: dict) -> Tuple[dict, dict]:
            await self._finish_tool_call(tool_call, tool_registry, mcp_session, step_dict)
            return tool_call, step_dict

        if parallel:
            finished = await asyncio.gather(*(run_one(tc, sd) for tc, sd in pending))
            for event in mcp_session.drain_process_events():
                process_trace.append(event.get("step") or {})
                yield event
            for tool_call, step_dict in finished:
                yield {"type": "process", "step": dict(step_dict)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": step_dict.get("result") or "",
                    }
                )
            return

        for tool_call, step_dict in pending:
            task = asyncio.create_task(
                run_one(tool_call, step_dict),
            )
            while not task.done():
                await asyncio.sleep(0.05)
                for event in mcp_session.drain_process_events():
                    process_trace.append(event.get("step") or {})
                    yield event
            await task
            for event in mcp_session.drain_process_events():
                process_trace.append(event.get("step") or {})
                yield event
            yield {"type": "process", "step": dict(step_dict)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "content": step_dict.get("result") or "",
                }
            )

    @staticmethod
    def _parse_tool_arguments(tool_call: dict) -> dict:
        func = tool_call.get("function") or {}
        raw_args = func.get("arguments") or "{}"
        try:
            return json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            return {}

    def _build_running_step(self, tool_call: dict, tool_registry: Dict[str, tuple]) -> dict:
        func = tool_call.get("function") or {}
        openai_name = func.get("name") or ""
        server, original_tool_name = tool_registry.get(openai_name, (None, openai_name))
        return McpStep(
            server=server.name if server else "MCP",
            tool=original_tool_name,
            arguments=self._parse_tool_arguments(tool_call),
            status="running",
        ).model_dump()

    @staticmethod
    async def _finish_tool_call(
            tool_call: dict,
            tool_registry: Dict[str, tuple],
            mcp_session: McpSessionManager,
            step_dict: dict,
    ) -> None:
        func = tool_call.get("function") or {}
        openai_name = func.get("name") or ""
        server, original_tool_name = tool_registry.get(openai_name, (None, openai_name))
        try:
            if not server:
                raise ValueError(f"未找到工具映射: {openai_name}")
            step_dict["result"] = await mcp_session.call_tool(
                server,
                original_tool_name,
                step_dict.get("arguments") or {},
                step_dict=step_dict,
            )
            step_dict["status"] = "done"
        except asyncio.CancelledError:
            if step_dict.get("status") != "cancelled":
                step_dict["status"] = "cancelled"
                step_dict["result"] = step_dict.get("result") or "已取消"
            raise
        except Exception as exc:
            step_dict["status"] = "error"
            step_dict["result"] = str(exc)

    @staticmethod
    async def _stream_final_answer(
            *,
            llm: OpenAICompatibleLLM,
            messages: List[dict],
            completion: dict,
            process_trace: List[dict],
            usage_acc: dict,
            llm_kwargs: dict,
    ) -> AsyncIterator[Dict[str, Any]]:
        final_content = (completion.get("content") or "").strip()
        if final_content:
            chunk_size = 8
            for i in range(0, len(final_content), chunk_size):
                yield {"type": "content", "content": final_content[i:i + chunk_size]}
                await asyncio.sleep(0.01)
        else:
            async for chunk in llm.stream_chat(messages=messages, **llm_kwargs):
                if chunk.get("type") == "usage":
                    merge_token_usage(usage_acc, chunk)
                    continue
                yield chunk

        yield {"type": "process_trace", "process_trace": process_trace}
        if any(usage_acc.values()):
            yield {"type": "usage", **usage_acc}
