# -*- coding: utf-8 -*-
"""混合智能体 system prompt 组装。"""
from __future__ import annotations

from typing import List

from backend.applications.agent.orchestrator.binding_resolver import ResolvedChatBinding
from backend.applications.mcp_client.adapters import build_mcp_metadata_block
from backend.configure.rag_config import (
    HYBRID_AGENT_CHAT_SKILL_SECTION,
    HYBRID_AGENT_CORE_SYSTEM_PROMPT,
    HYBRID_AGENT_MCP_TOOLS_SECTION,
    HYBRID_AGENT_RUN_SKILL_SECTION,
)


def build_hybrid_system_prompt(
        *,
        binding: ResolvedChatBinding,
        rag_prompt: str,
        extra_system: str = "",
        run_mode: bool = False,
) -> str:
    parts: List[str] = [HYBRID_AGENT_CORE_SYSTEM_PROMPT]

    if binding.chat_skill and binding.skill_instruction:
        if run_mode:
            parts.append(HYBRID_AGENT_RUN_SKILL_SECTION)
        else:
            parts.append(HYBRID_AGENT_CHAT_SKILL_SECTION)
        skill = binding.chat_skill
        parts.append(
            f"## Skill 指令（{skill.name} / {skill.skill_key}）\n\n{binding.skill_instruction}"
        )

    if binding.mcp_servers:
        parts.append(HYBRID_AGENT_MCP_TOOLS_SECTION)
        metadata = build_mcp_metadata_block(binding.mcp_servers)
        if metadata:
            parts.append(metadata)

    if extra_system:
        parts.append(extra_system)

    parts.append(f"---\n\n{rag_prompt}")
    return "\n\n".join(part for part in parts if part.strip())
