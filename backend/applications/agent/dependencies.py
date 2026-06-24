# -*- coding: utf-8 -*-
from backend.applications.agent.services.agent_crud import McpServerCrud, SkillCrud
from backend.applications.agent.services.skill_run_crud import SkillRunCrud


async def get_skill_crud() -> SkillCrud:
    return SkillCrud()


async def get_mcp_server_crud() -> McpServerCrud:
    return McpServerCrud()


async def get_skill_run_crud() -> SkillRunCrud:
    return SkillRunCrud()
