# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .agent_view import mcp_servers, skills
from .skill_run_view import skill_runs

skills_router = APIRouter()
mcp_servers_router = APIRouter()
skill_runs_router = APIRouter()

skills_router.include_router(skills)
mcp_servers_router.include_router(mcp_servers)
skill_runs_router.include_router(skill_runs)
