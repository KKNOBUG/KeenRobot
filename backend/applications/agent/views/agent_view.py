# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : agent_view.py
"""
import traceback

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from backend.applications.agent.dependencies import (
    get_mcp_server_crud,
    get_skill_crud,
    get_skill_run_crud,
)
from backend.applications.agent.schemas.skill_run_schema import (
    SkillStaleDraftCleanupQuery,
    SkillStaleDraftCleanupResult,
)
from backend.applications.agent.services.skill_run_crud import SkillRunCrud
from backend.applications.agent.schemas.agent_schema import (
    McpServerCreate,
    McpServerOut,
    McpServerUpdate,
    SkillCreate,
    SkillOut,
    SkillPreviewOut,
    SkillSyncResult,
    SkillUpdate,
    SkillUploadResult,
)
from backend.applications.agent.services.agent_crud import McpServerCrud, SkillCrud
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.core.responses import FailureResponse, NotFoundResponse, SuccessResponse
from backend.services import DependAuth

skills = APIRouter()
mcp_servers = APIRouter()


@skills.get("/", summary="Agent-查询技能列表")
async def list_skills(
        search: str = None,
        manage: bool = Query(default=False, description="管理页模式，包含已禁用项"),
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        items = await skill_crud.list_by_user(
            current_user.id, search=search, manage=manage
        )
        data = [SkillOut.model_validate(item).model_dump() for item in items]
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询技能列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@skills.post("/cleanup-stale-drafts", summary="Agent-清理长期未 start 的 draft Run")
async def cleanup_stale_skill_drafts(
        data: SkillStaleDraftCleanupQuery,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        result = await run_crud.cleanup_stale_drafts(
            current_user,
            days=data.days,
            dry_run=data.dry_run,
        )
        out = SkillStaleDraftCleanupResult.model_validate(result)
        msg = (
            f"预览：{out.scanned} 条可清理（超过 {out.stale_days} 天未开始）"
            if out.dry_run
            else f"已清理 {out.deleted} 条无效记录（扫描 {out.scanned} 条）"
        )
        return SuccessResponse(data=out.model_dump(), message=msg)
    except Exception as e:
        LOGGER.error(f"清理无效 draft Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"清理失败: {e}")


@skills.post("/sync", summary="Agent-同步磁盘 Skill")
async def sync_skills(
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        created, updated, removed, items = await skill_crud.sync_skills_for_user(
            current_user
        )
        data = SkillSyncResult(
            created=created,
            updated=updated,
            removed=removed,
            skills=[SkillOut.model_validate(item) for item in items],
        )
        return SuccessResponse(data=data.model_dump(), total=len(items))
    except Exception as e:
        LOGGER.error(f"同步技能失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"同步失败: {e}")


@skills.post("/upload", summary="Agent-上传 zip 安装 Skill")
async def upload_skill_zip(
        file: UploadFile = File(...),
        skill_key: str = Form(default=None),
        overwrite: bool = Form(default=False),
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            return FailureResponse(message="请上传 .zip 格式的 Skill 包")
        result = await skill_crud.upload_skill_zip(
            current_user,
            file,
            skill_key=skill_key or None,
            overwrite=overwrite,
        )
        out = SkillUploadResult.model_validate(result)
        return SuccessResponse(
            data=out.model_dump(),
            message=f"Skill「{out.name}」已安装到磁盘",
        )
    except ValueError as e:
        return FailureResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"上传 Skill zip 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"上传失败: {e}")


@skills.post("/", summary="Agent-新增技能")
async def create_skill(
        data: SkillCreate,
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        instance = await skill_crud.create_skill(current_user, data)
        return SuccessResponse(data=SkillOut.model_validate(instance).model_dump())
    except Exception as e:
        LOGGER.error(f"创建技能失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"创建失败: {e}")


@skills.get("/{skill_id}", summary="Agent-按id查询技能详情")
async def get_skill(
        skill_id: str,
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        instance = await skill_crud.get_skill(skill_id, current_user)
        return SuccessResponse(data=SkillOut.model_validate(instance).model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"查询技能详情失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@skills.put("/{skill_id}", summary="Agent-按id更新技能")
async def update_skill(
        skill_id: str,
        data: SkillUpdate,
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        instance = await skill_crud.update_skill(skill_id, current_user, data)
        return SuccessResponse(data=SkillOut.model_validate(instance).model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except ParameterException as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"更新技能失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败: {e}")


@skills.get("/{skill_id}/preview", summary="Agent-预览磁盘 Skill")
async def preview_skill(
        skill_id: str,
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        preview = await skill_crud.get_skill_preview(skill_id, current_user)
        return SuccessResponse(data=SkillPreviewOut.model_validate(preview).model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except ParameterException as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"预览技能失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"预览失败: {e}")


@skills.delete("/{skill_id}", summary="Agent-按id删除技能")
async def delete_skill(
        skill_id: str,
        current_user: User = DependAuth,
        skill_crud: SkillCrud = Depends(get_skill_crud),
):
    try:
        await skill_crud.delete_skill(skill_id, current_user)
        return SuccessResponse(message="技能已删除")
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"删除技能失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败: {e}")


@mcp_servers.get("/", summary="Agent-查询MCP服务列表")
async def list_mcp_servers(
        search: str = None,
        manage: bool = Query(default=False, description="管理页模式，包含已禁用项"),
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        items = await mcp_crud.list_by_user(
            current_user.id, search=search, manage=manage
        )
        data = [McpServerOut.model_validate(item).model_dump() for item in items]
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询MCP服务列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@mcp_servers.post("/", summary="Agent-新增MCP服务")
async def create_mcp_server(
        data: McpServerCreate,
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        instance = await mcp_crud.create_mcp_server(current_user, data)
        return SuccessResponse(data=McpServerOut.model_validate(instance).model_dump())
    except Exception as e:
        LOGGER.error(f"创建MCP服务失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"创建失败: {e}")


@mcp_servers.get("/{mcp_id}", summary="Agent-按id查询MCP服务详情")
async def get_mcp_server(
        mcp_id: str,
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        instance = await mcp_crud.get_mcp_server(mcp_id, current_user)
        return SuccessResponse(data=McpServerOut.model_validate(instance).model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"查询MCP服务详情失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@mcp_servers.put("/{mcp_id}", summary="Agent-按id更新MCP服务")
async def update_mcp_server(
        mcp_id: str,
        data: McpServerUpdate,
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        instance = await mcp_crud.update_mcp_server(mcp_id, current_user, data)
        return SuccessResponse(data=McpServerOut.model_validate(instance).model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"更新MCP服务失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败: {e}")


@mcp_servers.delete("/{mcp_id}", summary="Agent-按id删除MCP服务")
async def delete_mcp_server(
        mcp_id: str,
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        await mcp_crud.delete_mcp_server(mcp_id, current_user)
        return SuccessResponse(message="MCP 服务已删除")
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"删除MCP服务失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败: {e}")


@mcp_servers.post("/{mcp_id}/tools/refresh", summary="Agent-刷新MCP工具列表")
async def refresh_mcp_server_tools(
        mcp_id: str,
        current_user: User = DependAuth,
        mcp_crud: McpServerCrud = Depends(get_mcp_server_crud),
):
    try:
        instance = await mcp_crud.refresh_tools(mcp_id, current_user)
        tools = (instance.config or {}).get("tools") or []
        return SuccessResponse(data={"tools": tools, "total": len(tools)}, total=len(tools))
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except ValueError as e:
        return FailureResponse(message=str(e))
    except Exception as e:
        LOGGER.error(f"刷新MCP工具列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"刷新失败: {e}")
