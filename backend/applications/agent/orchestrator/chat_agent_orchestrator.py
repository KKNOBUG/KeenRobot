# -*- coding: utf-8 -*-
"""混合智能体统一 ReAct 编排：RAG + Skill + MCP + SSE。"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from backend.applications.agent.orchestrator.binding_resolver import resolve_chat_binding
from backend.applications.agent.orchestrator.context_builder import build_hybrid_system_prompt
from backend.applications.agent.orchestrator.tool_dispatcher import ToolDispatcher, ToolExecutionContext
from backend.applications.agent.policies.hybrid_agent_policy import HybridAgentPolicy
from backend.applications.base.rag.chain import (
    _resolve_system_prompt,
    _retrieve_context,
    is_irrelevant_question,
    stream_irrelevant_response,
)
from backend.applications.base.rag.llm import OpenAICompatibleLLM, format_messages, merge_token_usage
from backend.applications.mcp.audit import McpAuditContext, bind_mcp_audit_context, reset_mcp_audit_context
from backend.applications.mcp.cancel_scope import (
    McpCancelScope,
    bind_mcp_cancel_scope,
    get_mcp_cancel_scope,
    reset_mcp_cancel_scope,
)
from backend.applications.mcp.session_manager import McpSessionManager
from backend.applications.user.models.user_model import User

MCP_AGENT_SYSTEM_PROMPT = """你是一个可以调用外部 MCP 工具的智能助手。

规则：
1. 当用户问题需要地图、天气、实时数据等外部能力时，优先调用已提供的工具。
2. 工具返回结果后，用自然语言整理并回答用户。
3. 若无需工具即可回答，直接回复，不要强行调用工具。
4. 结合参考资料（若有）与工具结果给出准确、简洁的中文回答。
"""


class ChatAgentOrchestrator:
    async def stream(
            self,
            *,
            question: str,
            user: User,
            conversation_id: Optional[str] = None,
            skill_ids: Optional[List[str]] = None,
            mcp_server_ids: Optional[List[str]] = None,
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
            policy: Optional[HybridAgentPolicy] = None,
            extra_system: str = "",
            run_mode: bool = False,
            skill_run_id: Optional[str] = None,
            skill_cwd: Optional[Any] = None,
            skill_md_path: Optional[Any] = None,
            output_prefix: str = "output",
    ) -> AsyncIterator[Dict[str, Any]]:
        policy = policy or HybridAgentPolicy()
        audit_token = bind_mcp_audit_context(
            McpAuditContext(
                user_id=user.id,
                username=getattr(user, "username", None) or str(user.id),
                conversation_id=conversation_id,
                skill_id=skill_ids[0] if skill_ids else None,
                skill_run_id=skill_run_id,
            )
        )
        cancel_scope = McpCancelScope()
        cancel_token = bind_mcp_cancel_scope(cancel_scope)
        try:
            async for event in self._stream_impl(
                    question=question,
                    user=user,
                    conversation_id=conversation_id,
                    skill_ids=skill_ids or [],
                    mcp_server_ids=mcp_server_ids or [],
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
                    policy=policy,
                    extra_system=extra_system,
                    run_mode=run_mode,
                    skill_run_id=skill_run_id,
                    skill_cwd=skill_cwd,
                    skill_md_path=skill_md_path,
                    output_prefix=output_prefix,
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
            user: User,
            conversation_id: Optional[str],
            skill_ids: List[str],
            mcp_server_ids: List[str],
            knowledge_base_ids: Optional[List[str]],
            chat_history: Optional[List[Dict[str, str]]],
            model_name: str,
            api_key: str,
            base_url: str,
            temperature: float,
            max_tokens: int,
            top_p: float,
            system_prompt: str,
            top_k: int,
            score_threshold: float,
            max_history_rounds: int,
            enable_thinking: bool,
            policy: HybridAgentPolicy,
            extra_system: str,
            run_mode: bool,
            skill_run_id: Optional[str],
            skill_cwd,
            skill_md_path,
            output_prefix: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        if not skill_ids and not mcp_server_ids and not run_mode:
            if is_irrelevant_question(question):
                async for chunk in stream_irrelevant_response():
                    yield chunk
                return

        binding = await resolve_chat_binding(
            user=user,
            conversation_id=conversation_id,
            skill_ids=skill_ids or None,
            mcp_server_ids=mcp_server_ids or None,
            policy=policy,
            skill_cwd=skill_cwd,
            skill_md_path=skill_md_path,
            run_mode=run_mode,
        )

        if mcp_server_ids and not skill_ids and not binding.openai_tools:
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
        combined_system = build_hybrid_system_prompt(
            binding=binding,
            rag_prompt=rag_prompt,
            extra_system=extra_system,
            run_mode=run_mode,
        )
        messages = format_messages(
            system_prompt=combined_system,
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

        if not binding.openai_tools:
            async for chunk in llm.stream_chat(messages=messages, **llm_kwargs):
                if chunk.get("type") == "usage":
                    merge_token_usage(usage_acc, chunk)
                    continue
                yield chunk
            yield {"type": "process_trace", "process_trace": process_trace}
            if any(usage_acc.values()):
                yield {"type": "usage", **usage_acc}
            return

        tool_ctx = ToolExecutionContext(
            skill=binding.chat_skill,
            cwd=binding.chat_skill_cwd,
            include_write=policy.allow_skill_write,
            output_prefix=output_prefix,
        )
        dispatcher = ToolDispatcher(tool_ctx)

        async with McpSessionManager() as mcp_session:
            if binding.has_mcp_session:
                await mcp_session.open_servers(
                    binding.mcp_servers,
                    llm=llm,
                    policy=policy,
                    llm_kwargs=llm_kwargs,
                )
                tool_ctx.mcp_session = mcp_session

            if policy.inject_resource_contents and binding.mcp_servers and messages:
                if messages[0].get("role") == "system":
                    resource_ctx = await mcp_session.build_resource_context(
                        binding.mcp_servers,
                        max_chars=policy.max_injected_resource_chars,
                        max_per_server=policy.max_resources_per_server,
                    )
                    if resource_ctx:
                        messages[0]["content"] = f"{messages[0]['content']}\n\n{resource_ctx}"

            for _round in range(policy.max_tool_rounds):
                if skill_run_id:
                    from backend.applications.agent.services.skill_run_events import SkillRunEventHub

                    if SkillRunEventHub.is_cancelled(skill_run_id):
                        cancel_scope = get_mcp_cancel_scope()
                        if cancel_scope:
                            cancel_scope.request_cancel()
                        yield {"type": "error", "message": "Run 已取消"}
                        return
                if get_mcp_cancel_scope() and get_mcp_cancel_scope().is_cancelled():
                    raise asyncio.CancelledError("Chat agent cancelled")

                completion = await llm.chat_with_tools(
                    messages=messages,
                    tools=binding.openai_tools,
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
                            binding.tool_registry,
                            dispatcher,
                            binding.chat_skill,
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

        raise RuntimeError(f"工具调用超过最大轮次 {policy.max_tool_rounds}")

    async def _dispatch_tool_calls(
            self,
            tool_calls: List[dict],
            tool_registry: Dict[str, Any],
            dispatcher: ToolDispatcher,
            skill,
            mcp_session: McpSessionManager,
            messages: List[dict],
            process_trace: List[dict],
            *,
            parallel: bool,
    ) -> AsyncIterator[Dict[str, Any]]:
        pending: List[Tuple[dict, dict]] = []
        for tool_call in tool_calls:
            step_dict = dispatcher.build_running_step(tool_call, tool_registry, skill)
            process_trace.append(step_dict)
            yield {"type": "process", "step": step_dict}
            pending.append((tool_call, step_dict))

        async def run_one(tool_call: dict, step_dict: dict) -> Tuple[dict, dict]:
            func = tool_call.get("function") or {}
            openai_name = func.get("name") or ""
            arguments = dispatcher.parse_tool_arguments(tool_call)
            step_dict.setdefault("arguments", arguments)
            if step_dict.get("type") == "mcp":
                step_dict["arguments"] = arguments
            await dispatcher.execute(
                openai_name,
                arguments,
                registry=tool_registry,
                step_dict=step_dict,
            )
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
                        "content": dispatcher.result_text_from_step(step_dict),
                    }
                )
            return

        for tool_call, step_dict in pending:
            task = asyncio.create_task(run_one(tool_call, step_dict))
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
                    "content": dispatcher.result_text_from_step(step_dict),
                }
            )

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


# 兼容旧名称
McpAgentOrchestrator = ChatAgentOrchestrator
