# -*- coding: utf-8 -*-
"""混合智能体聊天绑定解析：Skill snapshot、MCP servers、工具 registry。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from backend.applications.agent.models.agent_model import McpServer, Skill
from backend.applications.agent.policies.hybrid_agent_policy import HybridAgentPolicy
from backend.applications.agent.services.agent_crud import McpServerCrud, SkillCrud
from backend.applications.agent.services.skill_file_tools import build_skill_openai_tools
from backend.applications.agent.services.skill_registry import ensure_chat_snapshot, parse_skill_md
from backend.applications.agent.services.skill_validation import resolve_embedded_mcp_ids
from backend.applications.mcp_client.adapters import build_openai_tool_specs
from backend.applications.user.models.user_model import User


@dataclass
class ToolRoute:
    kind: Literal["skill", "mcp"]
    skill_tool: Optional[str] = None
    mcp_server: Optional[McpServer] = None
    mcp_tool_name: Optional[str] = None


@dataclass
class ResolvedChatBinding:
    knowledge_base_ids: List[str] = field(default_factory=list)
    chat_skill: Optional[Skill] = None
    chat_skill_snapshot: Optional[Path] = None
    chat_skill_cwd: Optional[Path] = None
    skill_instruction: str = ""
    mcp_servers: List[McpServer] = field(default_factory=list)
    openai_tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_registry: Dict[str, ToolRoute] = field(default_factory=dict)
    has_mcp_session: bool = False


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


async def load_skill_for_binding(skill_id: str, user: User, *, run_mode: bool = False) -> Skill:
    crud = SkillCrud()
    skill = await crud.get_skill(skill_id, user)
    if not skill.is_enabled:
        raise ValueError(f"技能「{skill.name}」未启用")
    if not skill.skill_key:
        raise ValueError(f"技能「{skill.name}」未关联磁盘 Skill，请先在管理页同步")
    if not run_mode:
        mode = (skill.interaction_mode or "chat").lower()
        if mode != "chat":
            raise ValueError(f"技能「{skill.name}」需通过 Skill 向导执行")
    return skill


async def load_chat_skill(skill_id: str, user: User) -> Skill:
    return await load_skill_for_binding(skill_id, user, run_mode=False)


def load_skill_instruction(skill_md_path: Path) -> str:
    _, skill_body = parse_skill_md(skill_md_path)
    return skill_body.strip() or skill_md_path.read_text(encoding="utf-8")


def merge_mcp_server_lists(*lists: List[McpServer]) -> List[McpServer]:
    merged: List[McpServer] = []
    seen: set[str] = set()
    for servers in lists:
        for server in servers:
            if server.id in seen:
                continue
            seen.add(server.id)
            merged.append(server)
    return merged


def merge_openai_tools(
        primary: List[Dict[str, Any]],
        secondary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    used = {
        item.get("function", {}).get("name")
        for item in primary
        if item.get("function", {}).get("name")
    }
    merged = list(primary)
    for tool in secondary:
        name = tool.get("function", {}).get("name") or ""
        if name in used:
            continue
        merged.append(tool)
        used.add(name)
    return merged


def build_skill_tool_registry(
        *,
        include_write: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, ToolRoute]]:
    openai_tools, _ = build_skill_openai_tools(include_write=include_write)
    registry: Dict[str, ToolRoute] = {}
    for tool in openai_tools:
        name = tool.get("function", {}).get("name") or ""
        if not name:
            continue
        registry[name] = ToolRoute(kind="skill", skill_tool=name)
    return openai_tools, registry


def build_mcp_tool_registry(
        mcp_servers: List[McpServer],
) -> tuple[List[Dict[str, Any]], Dict[str, ToolRoute]]:
    openai_tools, mcp_map = build_openai_tool_specs(mcp_servers)
    registry: Dict[str, ToolRoute] = {}
    for openai_name, (server, original_tool_name) in mcp_map.items():
        registry[openai_name] = ToolRoute(
            kind="mcp",
            mcp_server=server,
            mcp_tool_name=original_tool_name,
        )
    return openai_tools, registry


async def resolve_chat_binding(
        *,
        user: User,
        conversation_id: Optional[str],
        skill_ids: Optional[List[str]],
        mcp_server_ids: Optional[List[str]],
        policy: HybridAgentPolicy,
        skill_cwd: Optional[Path] = None,
        skill_md_path: Optional[Path] = None,
        run_mode: bool = False,
) -> ResolvedChatBinding:
    binding = ResolvedChatBinding()

    chat_skill: Optional[Skill] = None
    if skill_ids:
        if len(skill_ids) > 1:
            raise ValueError("聊天仅支持选择一个 Skill")
        chat_skill = await load_skill_for_binding(skill_ids[0], user, run_mode=run_mode)
        binding.chat_skill = chat_skill
        if skill_md_path and skill_cwd:
            binding.chat_skill_snapshot = skill_md_path.parent
            binding.chat_skill_cwd = skill_cwd
            binding.skill_instruction = load_skill_instruction(skill_md_path)
        elif conversation_id:
            snapshot_dir = ensure_chat_snapshot(chat_skill.skill_key, user.id, conversation_id)
            binding.chat_skill_snapshot = snapshot_dir
            binding.chat_skill_cwd = snapshot_dir.parent
            binding.skill_instruction = load_skill_instruction(snapshot_dir / "SKILL.md")

    session_mcp: List[McpServer] = []
    if mcp_server_ids:
        session_mcp = await load_mcp_servers(mcp_server_ids, user)

    embedded_mcp: List[McpServer] = []
    if chat_skill and user:
        embedded_ids = resolve_embedded_mcp_ids(chat_skill.execution)
        if embedded_ids:
            embedded_mcp = await load_mcp_servers(embedded_ids, user)

    binding.mcp_servers = merge_mcp_server_lists(session_mcp, embedded_mcp)
    binding.has_mcp_session = bool(binding.mcp_servers)

    skill_tools: List[Dict[str, Any]] = []
    registry: Dict[str, ToolRoute] = {}
    if chat_skill:
        skill_tools, skill_registry = build_skill_tool_registry(
            include_write=policy.allow_skill_write,
        )
        registry.update(skill_registry)

    mcp_tools: List[Dict[str, Any]] = []
    if binding.mcp_servers:
        mcp_tools, mcp_registry = build_mcp_tool_registry(binding.mcp_servers)
        for name, route in mcp_registry.items():
            if name not in registry:
                registry[name] = route

    binding.openai_tools = merge_openai_tools(skill_tools, mcp_tools)
    binding.tool_registry = registry
    return binding
