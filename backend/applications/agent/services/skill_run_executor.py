# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_executor.py
"""
from __future__ import annotations

import traceback
from typing import Optional

from backend.applications.agent.models.agent_model import Skill, SkillRun
from backend.applications.agent.services.skill_run_events import SkillRunEventHub
from backend.applications.agent.services.workspace_service import WorkspaceService
from backend.applications.base.rag.skill_agent import skill_run_agent_stream
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.services.llm_connection import resolve_chat_llm_params
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER

DEFAULT_RUN_QUESTION = (
    "请严格按照 Skill 指令执行当前任务。"
    "用户输入已在 input/ 目录及结构化字段中提供，请将产物写入 output/ 目录，并给出简要执行摘要。"
)


def build_skill_run_ref(run: SkillRun, skill: Skill) -> dict:
    return {
        "run_id": run.id,
        "skill_id": skill.id,
        "skill_name": skill.name,
        "status": run.status,
        "links": [
            {
                "label": "查看执行记录",
                "path": f"/ai-manage/skill-runs?run={run.id}",
            }
        ],
    }


async def persist_skill_run_conversation_message(
        run: SkillRun,
        skill: Skill,
        content: str,
        *,
        process_trace: Optional[list] = None,
        usage_data: Optional[dict] = None,
) -> None:
    """Run 结束且绑定了 conversation_id 时，写入助手消息（含 skill_run_ref）。"""
    if not run.conversation_id:
        return
    from backend.enums.chat_session_enum import ChatMessageRole
    from backend.applications.conversation.services.conversation_crud import (
        ConversationCrud,
    )

    crud = ConversationCrud()
    conv = await crud.get_by_id(run.conversation_id, run.user_id)
    if not conv:
        return

    text = (content or "").strip()
    if not text:
        if run.status == "failed":
            text = run.error_message or f"Skill「{skill.name}」执行失败。"
        else:
            text = f"Skill「{skill.name}」任务已执行完成。"

    skill_run_ref = build_skill_run_ref(run, skill)
    exec_msg = await crud.message.find_execution_message(run.conversation_id, run.id)
    if not exec_msg:
        intake_msg = await crud.message.find_intake_message(run.conversation_id, run.id)
        if intake_msg:
            intake = dict(intake_msg.skill_intake or {})
            if intake.get("phase") not in ("submitted", "cancelled"):
                steps = (skill.input_schema or {}).get("wizard_steps") or []
                intake["phase"] = "submitted"
                if steps:
                    intake["step_index"] = len(steps) - 1
                intake.pop("run_summary", None)
                intake.pop("process_trace", None)
                intake_msg.skill_intake = intake
                await intake_msg.save()
        exec_msg = await crud.message.add_message(
            run.conversation_id,
            ChatMessageRole.ASSISTANT,
            text,
            prompt_tokens=(usage_data or {}).get("prompt_tokens"),
            completion_tokens=(usage_data or {}).get("completion_tokens"),
            reasoning_tokens=(usage_data or {}).get("reasoning_tokens"),
            process_trace=process_trace,
            skill_run_ref=skill_run_ref,
        )
        return

    exec_msg.content = text
    exec_msg.skill_run_ref = skill_run_ref
    if process_trace:
        exec_msg.process_trace = process_trace
    if usage_data:
        exec_msg.prompt_tokens = usage_data.get("prompt_tokens")
        exec_msg.completion_tokens = usage_data.get("completion_tokens")
        exec_msg.reasoning_tokens = usage_data.get("reasoning_tokens")
    await exec_msg.save()


async def _resolve_model_config(model_config_id: Optional[str]) -> Optional[ModelConfig]:
    if not model_config_id:
        return None
    return await ModelConfig.get_or_none(id=model_config_id, state__not=1)


async def execute_skill_run(
        run_id: str,
        user_id: int,
        question: Optional[str] = None,
        *,
        publish_events: bool = True,
) -> None:
    """执行 Skill Run 并在 wizard 模式下发布 SSE 事件。"""
    run = await SkillRun.get_or_none(id=run_id, state__not=1)
    if not run or run.user_id != user_id:
        LOGGER.error(f"Skill Run 不存在或无权限: {run_id}")
        return

    skill = await Skill.get_or_none(id=run.skill_id, state__not=1)
    if not skill:
        await _fail_run(run, "关联 Skill 不存在", publish_events)
        return

    workspace = WorkspaceService(run)
    full_response = ""
    process_trace = []
    usage_data = None

    try:
        run.status = "running"
        run.error_message = None
        await run.save()
        workspace.update_meta_status("running")
        if publish_events:
            SkillRunEventHub.mark_running(run_id)
            await SkillRunEventHub.publish(run_id, {"type": "meta", "run_id": run_id, "status": "running"})

        model_config = await _resolve_model_config(run.model_config_id)
        llm_params = resolve_chat_llm_params(model_config)
        effective_thinking = (
                model_config is not None
                and model_config.model_thinking
        )

        async for chunk in skill_run_agent_stream(
                run=run,
                skill=skill,
                question=question or DEFAULT_RUN_QUESTION,
                enable_thinking=effective_thinking,
                **llm_params,
        ):
            if SkillRunEventHub.is_cancelled(run_id):
                run.status = "cancelled"
                await run.save()
                workspace.update_meta_status("cancelled")
                if publish_events:
                    await SkillRunEventHub.publish(
                        run_id, {"type": "error", "message": "Run 已取消"}
                    )
                return

            if chunk.get("type") == "content":
                full_response += chunk.get("content") or ""
            elif chunk.get("type") == "process_trace":
                process_trace = chunk.get("process_trace") or process_trace
            elif chunk.get("type") == "usage":
                usage_data = {
                    "prompt_tokens": chunk.get("prompt_tokens"),
                    "completion_tokens": chunk.get("completion_tokens"),
                    "reasoning_tokens": chunk.get("reasoning_tokens"),
                }
            elif chunk.get("type") == "error":
                await _fail_run(run, chunk.get("message") or "执行失败", publish_events)
                return

            if publish_events:
                await SkillRunEventHub.publish(run_id, chunk)

        run.status = "completed"
        await run.save()
        workspace.update_meta_status("completed")

        await persist_skill_run_conversation_message(
            run,
            skill,
            full_response,
            process_trace=process_trace or None,
            usage_data=usage_data,
        )

        if publish_events:
            done_payload = {
                "type": "done",
                "content": full_response,
                "run_id": run_id,
                "status": "completed",
            }
            if process_trace:
                done_payload["process_trace"] = process_trace
            if usage_data:
                done_payload["usage"] = usage_data
            await SkillRunEventHub.publish(run_id, done_payload)

    except Exception as exc:
        LOGGER.error(f"Skill Run 执行失败: {run_id}\n{traceback.format_exc()}")
        await _fail_run(run, str(exc), publish_events)
    finally:
        if publish_events:
            await SkillRunEventHub.finish(run_id)
            SkillRunEventHub.cleanup(run_id)


async def _fail_run(run: SkillRun, message: str, publish_events: bool) -> None:
    run.status = "failed"
    run.error_message = message
    await run.save()
    workspace = WorkspaceService(run)
    workspace.update_meta_status("failed")
    skill = await Skill.get_or_none(id=run.skill_id, state__not=1)
    if skill:
        await persist_skill_run_conversation_message(
            run,
            skill,
            message,
        )
    if publish_events:
        await SkillRunEventHub.publish(
            run.id, {"type": "error", "message": message}
        )
