# -*- coding: utf-8 -*-
"""混合智能体 system prompt 组装。"""
from __future__ import annotations

from typing import List, Optional

from backend.applications.agent.orchestrator.binding_resolver import ResolvedChatBinding
from backend.applications.mcp.adapters import build_mcp_metadata_block

HYBRID_AGENT_BASE_PROMPT = """你是一个企业级混合智能助手，可根据会话绑定使用知识库、Skill 与 MCP 外部工具。

规则：
1. 结合参考资料（若有）与工具结果，用准确、简洁的中文回答用户。
2. 若无需工具即可回答，直接回复，不要强行调用工具。
3. 调用工具前确认确有需要；工具返回后整理为自然语言回复。
"""

CHAT_SKILL_WRAPPER = """## Skill Agent 能力包

你当前绑定了 Agent Skill，须严格遵循下方「Skill 指令」。
- 需要读取 Skill 包内文件或 Skill 指令要求时，使用 skill_read / skill_glob。
- chat 模式禁止使用 skill_write。
- 若同时绑定 MCP，仅当问题需要外部实时数据或 MCP 能力时调用 MCP 工具。
"""

MCP_AGENT_SECTION = """## MCP Agent 能力包

你当前绑定了外部 MCP 服务，可在需要地图、天气、实时数据等外部能力时调用已提供的 MCP 工具。
"""

SKILL_AGENT_WRAPPER = """你是一个按 Agent Skill 规范执行任务的智能助手。

规则：
1. 严格遵循下方「Skill 指令」中的流程与输出要求。
2. 需要读取模板、规则或脚本时，使用 skill_read / skill_glob 工具，不要臆造文件内容。
3. Run 模式下可将产物写入 output/ 目录（使用 skill_write）。
4. 结合参考资料（若有）完成任务，用简洁中文回复用户。
5. 输入文件位于 input/ 目录；Skill 知识位于 .skill_snapshot/ 目录。
6. 若已绑定 MCP 外部工具，需要实时数据或外部能力时可调用，与 Skill 文件工具配合使用。
"""


def build_hybrid_system_prompt(
        *,
        binding: ResolvedChatBinding,
        rag_prompt: str,
        extra_system: str = "",
        run_mode: bool = False,
) -> str:
    parts: List[str] = [HYBRID_AGENT_BASE_PROMPT]

    if binding.chat_skill and binding.skill_instruction:
        if run_mode:
            parts.append(SKILL_AGENT_WRAPPER)
        else:
            parts.append(CHAT_SKILL_WRAPPER)
        skill = binding.chat_skill
        parts.append(
            f"## Skill 指令（{skill.name} / {skill.skill_key}）\n\n{binding.skill_instruction}"
        )

    if binding.mcp_servers:
        parts.append(MCP_AGENT_SECTION)
        metadata = build_mcp_metadata_block(binding.mcp_servers)
        if metadata:
            parts.append(metadata)

    if extra_system:
        parts.append(extra_system)

    parts.append(f"---\n\n{rag_prompt}")
    return "\n\n".join(part for part in parts if part.strip())
