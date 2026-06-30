# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_agent.py
Skill Run 与聊天 Skill 入口；ReAct 编排已统一至 ChatAgentOrchestrator。
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.applications.agent.models.agent_model import Skill, SkillRun
from backend.applications.agent.orchestrator.chat_agent_orchestrator import ChatAgentOrchestrator
from backend.applications.agent.policies.hybrid_agent_policy import HybridAgentPolicy
from backend.applications.agent.services.workspace_service import WorkspaceService
from backend.applications.user.models.user_model import User

_chat_orchestrator = ChatAgentOrchestrator()


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


async def skill_agent_stream(
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]],
        skill_ids: List[str],
        user: User,
        conversation_id: str,
        mcp_ids: Optional[List[str]] = None,
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
    """Skill 智能体流式问答（chat 模式）→ 统一 ChatAgentOrchestrator。"""
    if not skill_ids:
        raise ValueError("未选择 Skill")
    async for chunk in _chat_orchestrator.stream(
            question=question,
            user=user,
            conversation_id=conversation_id,
            skill_ids=skill_ids,
            mcp_server_ids=mcp_ids or [],
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
            policy=HybridAgentPolicy(allow_skill_write=False),
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

    async for chunk in _chat_orchestrator.stream(
            question=question,
            user=user,
            conversation_id=run.conversation_id,
            skill_ids=[skill.id],
            mcp_server_ids=[],
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
            policy=HybridAgentPolicy(allow_skill_write=True, on_max_rounds="error"),
            extra_system=extra,
            run_mode=True,
            skill_run_id=run.id,
            skill_cwd=workspace.root,
            skill_md_path=skill_md_path,
            output_prefix=output_root,
    ):
        yield chunk
