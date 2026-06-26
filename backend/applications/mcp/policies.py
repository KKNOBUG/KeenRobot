# -*- coding: utf-8 -*-
from backend.applications.agent.policies.hybrid_agent_policy import (
    HybridAgentPolicy,
    MAX_HYBRID_TOOL_ROUNDS,
)

McpAgentPolicy = HybridAgentPolicy
MAX_MCP_TOOL_ROUNDS = MAX_HYBRID_TOOL_ROUNDS
