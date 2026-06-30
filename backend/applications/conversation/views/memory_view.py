# -*- coding: utf-8
"""M2 用户显式记忆 API。"""
import traceback

from fastapi import APIRouter, Depends

from backend.applications.conversation.schemas.memory_schema import UserMemoryCreate, UserMemoryOut
from backend.applications.conversation.services.user_memory_crud import (
    create_explicit_memory,
    list_active_memories,
    soft_delete_memory,
)
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.core.exceptions import ParameterException
from backend.core.responses import FailureResponse, NotFoundResponse, SuccessResponse
from backend.services import DependAuth

memory = APIRouter()


@memory.get("/memories", summary="我的记忆-列表")
async def list_user_memories(current_user: User = DependAuth):
    if not PROJECT_CONFIG.USER_MEMORY_ENABLED:
        return SuccessResponse(data=[])
    try:
        rows = await list_active_memories(current_user.id)
        data = [UserMemoryOut.model_validate(row).model_dump() for row in rows]
        return SuccessResponse(data=data, total=len(data))
    except Exception as exc:
        LOGGER.error(f"查询用户记忆失败: {exc}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {exc}")


@memory.post("/memories", summary="我的记忆-手动新增")
async def create_user_memory(body: UserMemoryCreate, current_user: User = DependAuth):
    try:
        record = await create_explicit_memory(
            current_user,
            body.content,
            memory_key=body.memory_key,
        )
        data = UserMemoryOut.model_validate(record).model_dump()
        return SuccessResponse(data=data, message="记忆已保存")
    except ParameterException as exc:
        return FailureResponse(message=exc.message)
    except Exception as exc:
        LOGGER.error(f"创建用户记忆失败: {exc}\n{traceback.format_exc()}")
        return FailureResponse(message=f"保存失败: {exc}")


@memory.delete("/memories/{memory_id}", summary="我的记忆-删除")
async def delete_user_memory(memory_id: str, current_user: User = DependAuth):
    try:
        ok = await soft_delete_memory(current_user.id, memory_id)
        if not ok:
            return NotFoundResponse(message="记忆不存在或已删除")
        return SuccessResponse(message="已删除")
    except Exception as exc:
        LOGGER.error(f"删除用户记忆失败: {exc}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败: {exc}")
