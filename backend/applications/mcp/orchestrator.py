# -*- coding: utf-8 -*-
"""MCP 集成层：向后兼容 re-export，实现已迁至 agent.orchestrator。"""
from backend.applications.agent.orchestrator.binding_resolver import load_mcp_servers
from backend.applications.agent.orchestrator.chat_agent_orchestrator import (
    ChatAgentOrchestrator,
    McpAgentOrchestrator,
)
from backend.configure.rag_config import MCP_AGENT_STANDALONE_SYSTEM_PROMPT

__all__ = [
    "MCP_AGENT_STANDALONE_SYSTEM_PROMPT",
    "ChatAgentOrchestrator",
    "McpAgentOrchestrator",
    "load_mcp_servers",
]
