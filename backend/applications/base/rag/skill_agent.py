# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_agent.py
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.applications.agent.models.agent_model import Skill, SkillRun
from backend.applications.agent.services.agent_crud import SkillCrud
from backend.applications.agent.services.mcp_tools import (
    build_openai_tool_specs,
    call_remote_tool,
)
from backend.applications.agent.services.skill_file_tools import (
    build_skill_openai_tools,
    execute_skill_tool,
)
from backend.applications.agent.services.skill_registry import (
    ensure_chat_snapshot,
    parse_skill_md,
)
from backend.applications.agent.services.skill_run_events import SkillRunEventHub
from backend.applications.agent.services.skill_validation import resolve_embedded_mcp_ids
from backend.applications.agent.services.workspace_service import WorkspaceService
from backend.applications.base.rag.chain import _resolve_system_prompt, _retrieve_context
from backend.applications.base.rag.llm import OpenAICompatibleLLM, format_messages
from backend.applications.base.rag.mcp_agent import _load_mcp_servers
from backend.applications.conversation.schemas.process_step_schema import McpStep, SkillStep
from backend.applications.user.models.user_model import User

MAX_SKILL_TOOL_ROUNDS = 8

SKILL_AGENT_WRAPPER = """你是一个按 Agent Skill 规范执行任务的智能助手。

规则：
1. 严格遵循下方「Skill 指令」中的流程与输出要求。
2. 需要读取模板、规则或脚本时，使用 skill_read / skill_glob 工具，不要臆造文件内容。
3. Run 模式下可将产物写入 output/ 目录（使用 skill_write）。
4. 结合参考资料（若有）完成任务，用简洁中文回复用户。
5. 输入文件位于 input/ 目录；Skill 知识位于 .skill_snapshot/ 目录。
6. 若已绑定 MCP 外部工具，需要实时数据或外部能力时可调用，与 Skill 文件工具配合使用。
"""

CHAT_SKILL_WRAPPER = """你是一个绑定了 Agent Skill 的聊天助手。

规则：
1. 遵循下方「Skill 指令」中的流程与输出要求。
2. **普通对话**（推理、写作、答疑、闲聊等）直接回答，**不要**调用 skill_read / skill_glob。
3. 仅当用户明确要求读取 Skill 包内文件、执行联调命令（如 ping / checklist / glob）或 Skill 指令规定必须用工具时，才调用 Skill 文件工具。
4. 结合参考资料（若有）完成任务，用简洁中文回复用户。
5. Skill 知识位于 .skill_snapshot/ 目录；chat 模式不要使用 skill_write。
6. 若已绑定 MCP 外部工具，仅在问题确实需要外部实时数据时调用 MCP 工具。
"""

# chat 模式默认「按需工具」：命中以下模式才进入 tool-calling 链路
_CHAT_TOOL_TRIGGER_PATTERNS = (
    r"(?i)\bping\b",
    r"自检",
    r"checklist|清单",
    r"(?i)skill_(read|glob|write)",
    r"\.skill_snapshot",
    r"读取.{0,12}(checklist|清单|规则|模板|文件|demo|scenarios)",
    r"(?i)\bglob\b",
    r"快照",
    r"(?i)test_chat",
    r"demo\.md",
    r"能做什么|你会什么|支持什么|使用说明|联调命令",
    r"(?i)\bhelp\b",
    r"扫描\s*文件|列出\s*文件|读取\s*skill|glob\s*扫描",
)


def _resolve_chat_tools_policy(skill: Skill) -> str:
    schema = skill.input_schema or {}
    policy = (schema.get("chat_tools") or "on_demand").strip().lower()
    if policy not in {"on_demand", "always"}:
        return "on_demand"
    return policy


def _question_needs_skill_tools(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in _CHAT_TOOL_TRIGGER_PATTERNS)


async def _load_embedded_mcp_tools(
        skill: Skill,
        user: User,
) -> tuple[List[Any], Dict[str, tuple]]:
    mcp_ids = resolve_embedded_mcp_ids(skill.execution)
    if not mcp_ids or not user:
        return [], {}
    servers = await _load_mcp_servers(mcp_ids, user)
    openai_tools, registry = build_openai_tool_specs(servers)
    return openai_tools, registry


def _merge_openai_tools(
        skill_tools: List[Dict[str, Any]],
        mcp_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    used = {
        item.get("function", {}).get("name")
        for item in skill_tools
        if item.get("function", {}).get("name")
    }
    merged = list(skill_tools)
    for tool in mcp_tools:
        name = tool.get("function", {}).get("name") or ""
        if name in used:
            continue
        merged.append(tool)
        used.add(name)
    return merged


async def _execute_agent_tool(
        *,
        cwd: Path,
        tool_name: str,
        arguments: Dict[str, Any],
        skill: Skill,
        mcp_registry: Dict[str, tuple],
        output_prefix: str,
        include_write: bool,
) -> tuple[str, dict]:
    skill_tool_names = {"skill_read", "skill_glob"}
    if include_write:
        skill_tool_names.add("skill_write")

    if tool_name in skill_tool_names:
        step = SkillStep(
            skill_id=skill.id,
            name=tool_name,
            input=arguments,
            status="running",
        )
        step_dict = step.model_dump()
        try:
            result_text = execute_skill_tool(
                cwd,
                tool_name,
                arguments,
                output_prefix=output_prefix,
            )
            step_dict["status"] = "done"
            step_dict["output"] = result_text
        except Exception as exc:
            step_dict["status"] = "error"
            step_dict["output"] = str(exc)
        return step_dict.get("output") or "", step_dict

    if tool_name not in mcp_registry:
        step = SkillStep(
            skill_id=skill.id,
            name=tool_name,
            input=arguments,
            status="error",
        )
        step_dict = step.model_dump()
        step_dict["output"] = f"未知工具: {tool_name}"
        return step_dict["output"], step_dict

    server, original_tool_name = mcp_registry[tool_name]
    server_name = server.name if server else "MCP"
    step = McpStep(
        server=server_name,
        tool=original_tool_name,
        arguments=arguments,
        status="running",
    )
    step_dict = step.model_dump()
    try:
        if not server:
            raise ValueError(f"未找到 MCP 工具映射: {tool_name}")
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
    return step_dict.get("result") or "", step_dict


async def _load_chat_skill(skill_id: str, user: User) -> Skill:
    crud = SkillCrud()
    skill = await crud.get_skill(skill_id, user)
    if not skill.is_enabled:
        raise ValueError(f"技能「{skill.name}」未启用")
    if not skill.skill_key:
        raise ValueError(f"技能「{skill.name}」未关联磁盘 Skill，请先在管理页同步")
    mode = (skill.interaction_mode or "chat").lower()
    if mode != "chat":
        raise ValueError(f"技能「{skill.name}」需通过 Skill 向导执行")
    return skill


def _merge_usage(accumulator: Dict[str, int], part: Optional[Dict[str, Any]]) -> None:
    if not part:
        return
    for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens"):
        accumulator[key] = (accumulator.get(key) or 0) + (part.get(key) or 0)


def _load_skill_instruction(skill_md_path: Path) -> str:
    _, skill_body = parse_skill_md(skill_md_path)
    return skill_body.strip() or skill_md_path.read_text(encoding="utf-8")


def _build_run_context_note(run: SkillRun, workspace: WorkspaceService) -> str:
    lines = [
        "## Run 上下文",
        f"- run_id: {run.id}",
        f"- skill_key: {run.skill_key}",
        f"- 工作区根目录: {workspace.root.as_posix()}",
        f"- 输入目录: {workspace.input_dir.as_posix()}",
        f"- 输出目录: {workspace.output_dir.as_posix()}",
        f"- Skill 快照: {workspace.snapshot_dir.as_posix()}",
    ]
    if run.input_data:
        lines.append(f"- 结构化输入: {json.dumps(run.input_data, ensure_ascii=False)}")
    return "\n".join(lines)


async def _skill_agent_loop(
        *,
        question: str,
        skill: Skill,
        cwd: Path,
        skill_md_path: Path,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]],
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
        include_write: bool = False,
        output_prefix: str = "output",
        run_id: Optional[str] = None,
        extra_system: str = "",
        use_tools: bool = True,
        chat_mode: bool = False,
        user: Optional[User] = None,
) -> AsyncIterator[Dict[str, Any]]:
    skill_instruction = _load_skill_instruction(skill_md_path)

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
    wrapper = CHAT_SKILL_WRAPPER if chat_mode else SKILL_AGENT_WRAPPER
    combined_system = (
        f"{wrapper}\n\n"
        f"## Skill 指令（{skill.name} / {skill.skill_key}）\n\n"
        f"{skill_instruction}\n\n"
    )
    if extra_system:
        combined_system += f"{extra_system}\n\n"
    combined_system += f"---\n\n{rag_prompt}"

    messages = format_messages(
        system_prompt=combined_system,
        user_question=question,
        context=context,
        chat_history=chat_history,
        max_history_rounds=max_history_rounds,
        format_context=False,
    )

    openai_tools, _ = build_skill_openai_tools(include_write=include_write)
    mcp_tools, mcp_registry = await _load_embedded_mcp_tools(skill, user) if user else ([], {})
    if mcp_tools:
        openai_tools = _merge_openai_tools(openai_tools, mcp_tools)
    llm = OpenAICompatibleLLM(model=model_name, api_key=api_key, base_url=base_url)
    process_trace: List[dict] = []
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0}

    if not use_tools:
        async for chunk in llm.stream_chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                enable_thinking=enable_thinking,
        ):
            if chunk.get("type") == "usage":
                _merge_usage(usage_acc, chunk)
                continue
            yield chunk
        yield {"type": "process_trace", "process_trace": process_trace}
        if any(usage_acc.values()):
            yield {"type": "usage", **usage_acc}
        return

    for _round in range(MAX_SKILL_TOOL_ROUNDS):
        if run_id and SkillRunEventHub.is_cancelled(run_id):
            yield {"type": "error", "message": "Run 已取消"}
            return

        completion = await llm.chat_with_tools(
            messages=messages,
            tools=openai_tools,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            enable_thinking=enable_thinking,
        )
        _merge_usage(usage_acc, completion.get("usage"))

        tool_calls = completion.get("tool_calls") or []
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": completion.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                func = tool_call.get("function") or {}
                tool_name = func.get("name") or ""
                raw_args = func.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}

                result_text, step_dict = await _execute_agent_tool(
                    cwd=cwd,
                    tool_name=tool_name,
                    arguments=arguments,
                    skill=skill,
                    mcp_registry=mcp_registry,
                    output_prefix=output_prefix,
                    include_write=include_write,
                )
                process_trace.append(step_dict)
                yield {"type": "process", "step": dict(step_dict)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": result_text,
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
                    _merge_usage(usage_acc, chunk)
                    continue
                yield chunk

        yield {"type": "process_trace", "process_trace": process_trace}
        if any(usage_acc.values()):
            yield {"type": "usage", **usage_acc}
        return

    raise RuntimeError(f"Skill 工具调用超过最大轮次 {MAX_SKILL_TOOL_ROUNDS}")


async def skill_agent_stream(
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]],
        skill_ids: List[str],
        user: User,
        conversation_id: str,
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
    """Skill 智能体流式问答（chat 模式）。"""
    if not skill_ids:
        raise ValueError("未选择 Skill")
    if len(skill_ids) > 1:
        raise ValueError("聊天仅支持选择一个 Skill")

    skill = await _load_chat_skill(skill_ids[0], user)
    snapshot_dir = ensure_chat_snapshot(skill.skill_key, user.id, conversation_id)
    # 与 Run 模式一致：cwd 为工作区根，Skill 文件位于 .skill_snapshot/ 下
    chat_workspace = snapshot_dir.parent
    skill_md_path = snapshot_dir / "SKILL.md"
    tools_policy = _resolve_chat_tools_policy(skill)
    has_embedded_mcp = bool(resolve_embedded_mcp_ids(skill.execution))
    use_tools = (
        tools_policy == "always"
        or _question_needs_skill_tools(question)
        or has_embedded_mcp
    )

    async for chunk in _skill_agent_loop(
            question=question,
            skill=skill,
            cwd=chat_workspace,
            skill_md_path=skill_md_path,
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
            include_write=False,
            use_tools=use_tools,
            chat_mode=True,
            user=user,
    ):
        yield chunk


async def skill_run_agent_stream(
        run: SkillRun,
        skill: Skill,
        question: str,
        *,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        system_prompt: str = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        max_history_rounds: int = 0,
        enable_thinking: bool = False,
        user: Optional[User] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Skill Run 工作区流式执行（wizard / async_job）。"""
    if user is None:
        user = await User.get_or_none(id=run.user_id, state__not=1)
    workspace = WorkspaceService(run)
    skill_md_path = workspace.snapshot_dir / "SKILL.md"
    if not skill_md_path.is_file():
        raise FileNotFoundError("Run 快照缺少 SKILL.md")

    input_schema = skill.input_schema or {}
    _, output_root = workspace.layout_roots(input_schema)
    extra = _build_run_context_note(run, workspace)
    kb_ids = run.knowledge_base_ids or []

    async for chunk in _skill_agent_loop(
            question=question,
            skill=skill,
            cwd=workspace.root,
            skill_md_path=skill_md_path,
            knowledge_base_ids=kb_ids,
            chat_history=[],
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
            include_write=True,
            output_prefix=output_root,
            run_id=run.id,
            extra_system=extra,
            user=user,
    ):
        yield chunk
