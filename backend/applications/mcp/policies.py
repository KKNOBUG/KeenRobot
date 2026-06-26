# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Literal

MAX_MCP_TOOL_ROUNDS = 10


@dataclass
class McpAgentPolicy:
    max_tool_rounds: int = MAX_MCP_TOOL_ROUNDS
    parallel_tool_calls: bool = True
    on_max_rounds: Literal["error", "summarize"] = "error"
    inject_resource_contents: bool = True
    max_injected_resource_chars: int = 8000
    max_resources_per_server: int = 5
    sampling_mode: Literal["reject", "llm"] = "llm"
    log_mcp_progress: bool = True
    audit_enabled: bool = True
    audit_max_chars: int = 4096
