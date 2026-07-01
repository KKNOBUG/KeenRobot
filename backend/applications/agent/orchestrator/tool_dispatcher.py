# -*- coding: utf-8 -*-
"""Skill / MCP 工具统一分发。"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from backend.applications.agent.models.agent_model import Skill
from backend.applications.agent.orchestrator.binding_resolver import ToolRoute
from backend.applications.agent.services.skill_file_tools import execute_skill_tool
from backend.applications.conversation.schemas.process_step_schema import McpStep, SkillStep
from backend.applications.mcp_client.session_manager import McpSessionManager


@dataclass
class ToolExecutionContext:
    skill: Optional[Skill]
    cwd: Optional[Path]
    output_prefix: str = "output"
    include_write: bool = False
    mcp_session: Optional[McpSessionManager] = None


class ToolDispatcher:
    def __init__(self, ctx: ToolExecutionContext) -> None:
        self._ctx = ctx

    @staticmethod
    def parse_tool_arguments(tool_call: dict) -> dict:
        func = tool_call.get("function") or {}
        raw_args = func.get("arguments") or "{}"
        try:
            return json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def build_running_step(
            tool_call: dict,
            registry: Dict[str, ToolRoute],
            skill: Optional[Skill],
    ) -> dict:
        func = tool_call.get("function") or {}
        openai_name = func.get("name") or ""
        arguments = ToolDispatcher.parse_tool_arguments(tool_call)
        route = registry.get(openai_name)

        if route and route.kind == "skill":
            return SkillStep(
                skill_id=skill.id if skill else None,
                name=route.skill_tool or openai_name,
                input=arguments,
                status="running",
            ).model_dump()

        server = route.mcp_server if route else None
        tool_name = route.mcp_tool_name if route else openai_name
        return McpStep(
            server=server.name if server else "MCP",
            tool=tool_name,
            arguments=arguments,
            status="running",
        ).model_dump()

    async def execute(
            self,
            openai_tool_name: str,
            arguments: Dict[str, Any],
            *,
            registry: Dict[str, ToolRoute],
            step_dict: dict,
    ) -> str:
        route = registry.get(openai_tool_name)
        if route is None:
            step_dict["status"] = "error"
            if step_dict.get("type") == "skill":
                step_dict["output"] = f"未知工具: {openai_tool_name}"
                return step_dict["output"]
            step_dict["result"] = f"未知工具: {openai_tool_name}"
            return step_dict["result"]

        if route.kind == "skill":
            return await self._execute_skill(route.skill_tool or openai_tool_name, arguments, step_dict)

        return await self._execute_mcp(route, arguments, step_dict)

    async def _execute_skill(
            self,
            tool_name: str,
            arguments: Dict[str, Any],
            step_dict: dict,
    ) -> str:
        if not self._ctx.cwd:
            step_dict["status"] = "error"
            step_dict["output"] = "Skill 工作区未初始化"
            return step_dict["output"]
        try:
            result_text = execute_skill_tool(
                self._ctx.cwd,
                tool_name,
                arguments,
                output_prefix=self._ctx.output_prefix,
            )
            step_dict["status"] = "done"
            step_dict["output"] = result_text
            return result_text
        except Exception as exc:
            step_dict["status"] = "error"
            step_dict["output"] = str(exc)
            return step_dict["output"]

    async def _execute_mcp(
            self,
            route: ToolRoute,
            arguments: Dict[str, Any],
            step_dict: dict,
    ) -> str:
        session = self._ctx.mcp_session
        server = route.mcp_server
        tool_name = route.mcp_tool_name or ""
        if session is None or not server:
            step_dict["status"] = "error"
            step_dict["result"] = f"未找到 MCP 工具映射: {tool_name}"
            return step_dict["result"]
        try:
            result_text = await session.call_tool(
                server,
                tool_name,
                arguments,
                step_dict=step_dict,
            )
            step_dict["status"] = "done"
            step_dict["result"] = result_text
            return result_text
        except asyncio.CancelledError:
            if step_dict.get("status") != "cancelled":
                step_dict["status"] = "cancelled"
                step_dict["result"] = step_dict.get("result") or "已取消"
            raise
        except Exception as exc:
            step_dict["status"] = "error"
            step_dict["result"] = str(exc)
            return step_dict["result"]

    @staticmethod
    def result_text_from_step(step_dict: dict) -> str:
        if step_dict.get("type") == "skill":
            return step_dict.get("output") or ""
        return step_dict.get("result") or ""
