# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : history_view.py
@DateTime: 2026/6/9
"""
import traceback

from fastapi import APIRouter, Depends

from backend.applications.conversation.dependencies import get_conversation_crud
from backend.applications.conversation.schemas.conversation_schema import (
    ConversationDetail,
    ConversationOut,
    ConversationBindingsUpdate,
    SkillIntakeStart,
    SkillIntakeStartResult,
    SkillIntakeUpdate,
    MessageOut,
)
from backend.applications.conversation.services.conversation_crud import ConversationCrud
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.core.responses import SuccessResponse, FailureResponse, NotFoundResponse
from backend.services import DependAuth

history = APIRouter()


@history.post("/", summary="对话历史-创建新对话")
async def create_conversation(
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        conv = await conversation_crud.create_for_user(current_user.id)
        data = ConversationOut.model_validate(conv).model_dump()
        return SuccessResponse(data=data)
    except Exception as e:
        LOGGER.error(f"创建对话失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"创建失败: {e}")


@history.get("/", summary="对话历史-查询对话列表")
async def list_conversations(
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        items = await conversation_crud.list_by_user(current_user.id)
        data = [
            ConversationOut.model_validate(item).model_dump()
            for item in items
        ]
        return SuccessResponse(data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"查询对话列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@history.get("/{conversation_id}", summary="对话历史-按id查询对话详情")
async def get_conversation(
        conversation_id: str,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        conv = await conversation_crud.get_conversation(conversation_id, current_user)
        data = ConversationDetail.model_validate(conv).model_dump()
        return SuccessResponse(data=data)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"查询对话详情失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@history.put("/{conversation_id}/bindings", summary="对话-同步会话绑定")
async def sync_conversation_bindings(
        conversation_id: str,
        data: ConversationBindingsUpdate,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        conv = await conversation_crud.sync_conversation_bindings(
            current_user,
            conversation_id,
            data,
        )
        out = ConversationOut.model_validate(conv).model_dump()
        return SuccessResponse(data=out, message="会话绑定已更新")
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"同步会话绑定失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败: {e}")


@history.post("/{conversation_id}/skill-intake/start", summary="对话-Skill 收集开始")
async def start_skill_intake(
        conversation_id: str,
        data: SkillIntakeStart,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        result = await conversation_crud.start_skill_intake(
            current_user,
            conversation_id,
            data.skill_id,
            model_config_id=data.model_config_id,
            knowledge_base_ids=data.knowledge_base_ids,
            enable_thinking=data.enable_thinking,
            force_new=data.force_new,
        )
        out = SkillIntakeStartResult.model_validate(result)
        msg = "已恢复未完成的 Skill 收集" if out.resumed else "Skill 收集已开始"
        return SuccessResponse(data=out.model_dump(), message=msg)
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"开始 Skill 收集失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"开始失败: {e}")


@history.put(
    "/{conversation_id}/messages/{message_id}/skill-intake",
    summary="对话-更新 Skill 收集面板状态",
)
async def update_skill_intake_message(
        conversation_id: str,
        message_id: int,
        data: SkillIntakeUpdate,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        conv = await conversation_crud.get_by_id(conversation_id, current_user.id)
        if not conv:
            return NotFoundResponse(message="对话不存在")
        message = await conversation_crud.message.update_skill_intake(
            message_id, conversation_id, data
        )
        out = MessageOut.model_validate(message)
        return SuccessResponse(data=out.model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"更新 Skill 收集状态失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败: {e}")


@history.delete("/{conversation_id}", summary="对话历史-按id删除对话")
async def delete_conversation(
        conversation_id: str,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        await conversation_crud.delete_conversation(conversation_id, current_user)
        return SuccessResponse(message="已删除")
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"删除对话失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败: {e}")


@history.delete("/", summary="对话历史-清空所有对话")
async def clear_all_conversations(
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    try:
        await conversation_crud.clear_by_user(current_user.id)
        return SuccessResponse(message="已清空所有对话")
    except Exception as e:
        LOGGER.error(f"清空对话失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"清空失败: {e}")
