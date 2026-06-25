# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_crud.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import UploadFile

from backend.applications.agent.models.agent_model import Skill, SkillRun
from backend.applications.agent.schemas.skill_run_schema import SkillRunCreate
from backend.applications.agent.services.agent_crud import SkillCrud
from backend.applications.agent.services.skill_run_validator import (
    list_output_files,
    validate_run_inputs,
)
from backend.applications.agent.services.skill_run_executor import execute_skill_run
from backend.applications.agent.services.skill_run_events import SkillRunEventHub
from backend.applications.agent.services.workspace_service import WorkspaceService
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.conversation.models.conversation_model import Conversation
from backend.applications.knowledge_base.services.knowledge_base_crud import KnowledgeBaseCrud
from backend.applications.user.models.user_model import User
from backend.configure import PROJECT_CONFIG
from backend.core.exceptions import NotFoundException, ParameterException


class SkillRunCrud(ScaffoldCrud):
    TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
    DRAFT_STATUSES = frozenset({"pending", "validated"})
    RUN_MODES = frozenset({"wizard", "async_job"})

    def __init__(self):
        super().__init__(model=SkillRun)
        self.skill_crud = SkillCrud()

    async def get_by_id(self, run_id: str) -> Optional[SkillRun]:
        return await self.model.get_or_none(id=run_id, state__not=1)

    def check_access(self, run: SkillRun, user: User) -> None:
        if run.user_id != user.id:
            raise NotFoundException(message="Skill Run 不存在")

    async def get_run(self, run_id: str, user: User) -> SkillRun:
        run = await self.get_by_id(run_id)
        if not run:
            raise NotFoundException(message="Skill Run 不存在")
        self.check_access(run, user)
        return run

    async def _load_skill_for_run(self, skill_id: str, user: User) -> Skill:
        skill = await self.skill_crud.get_skill(skill_id, user)
        if not skill.is_enabled:
            raise ParameterException(message=f"技能「{skill.name}」未启用")
        mode = (skill.interaction_mode or "chat").lower()
        if mode not in self.RUN_MODES:
            raise ParameterException(
                message=f"技能「{skill.name}」为 {mode} 模式，"
                f"{'请直接在聊天中使用' if mode == 'chat' else '配置无效'}"
            )
        if not skill.skill_key:
            raise ParameterException(message=f"技能「{skill.name}」未关联磁盘 Skill")
        if not skill.input_schema:
            raise ParameterException(message=f"技能「{skill.name}」未配置 input_schema")
        return skill

    async def _validate_conversation(
            self, conversation_id: Optional[str], user: User
    ) -> None:
        if not conversation_id:
            return
        conv = await Conversation.get_or_none(
            id=conversation_id, user_id=user.id, state__not=1
        )
        if not conv:
            raise NotFoundException(message="对话不存在")

    async def _validate_knowledge_bases(
            self, knowledge_base_ids: Optional[List[str]], user: User
    ) -> None:
        if not knowledge_base_ids:
            return
        kb_crud = KnowledgeBaseCrud()
        for kb_id in knowledge_base_ids:
            kb = await kb_crud.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=f"知识库 {kb_id} 不存在")
            kb_crud.check_access(kb, user)

    async def create_run(self, user: User, data: SkillRunCreate) -> SkillRun:
        skill = await self._load_skill_for_run(data.skill_id, user)
        await self._validate_conversation(data.conversation_id, user)
        await self._validate_knowledge_bases(data.knowledge_base_ids, user)

        run = await self.create(
            {
                "user_id": user.id,
                "skill_id": skill.id,
                "skill_key": skill.skill_key,
                "skill_version": skill.skill_version,
                "interaction_mode": skill.interaction_mode,
                "conversation_id": data.conversation_id,
                "model_config_id": data.model_config_id,
                "knowledge_base_ids": data.knowledge_base_ids,
                "input_data": {},
                "status": "pending",
            }
        )

        workspace = WorkspaceService(run)
        workspace.init_draft_workspace(skill_version=skill.skill_version or "")
        return run

    async def get_active_draft(
            self,
            user: User,
            conversation_id: str,
            *,
            skill_id: Optional[str] = None,
    ) -> Optional[SkillRun]:
        if not conversation_id:
            return None
        qs = self.model.filter(
            user_id=user.id,
            state__not=1,
            conversation_id=conversation_id,
            status__in=list(self.DRAFT_STATUSES),
        )
        if skill_id:
            qs = qs.filter(skill_id=skill_id)
        return await qs.order_by("-created_time").first()

    async def list_runs(
            self,
            user: User,
            *,
            page: int = 1,
            page_size: int = 10,
            skill_id: Optional[str] = None,
            status: Optional[str] = None,
            conversation_id: Optional[str] = None,
            include_drafts: bool = False,
    ) -> Tuple[int, List[SkillRun]]:
        qs = self.model.filter(user_id=user.id, state__not=1)
        if skill_id:
            qs = qs.filter(skill_id=skill_id)
        if status:
            qs = qs.filter(status=status)
        elif not include_drafts:
            qs = qs.exclude(status__in=list(self.DRAFT_STATUSES))
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        total = await qs.count()
        items = (
            await qs.order_by("-created_time")
            .offset((page - 1) * page_size)
            .limit(page_size)
            .prefetch_related("skill")
        )
        return total, items

    async def _get_skill(self, run: SkillRun) -> Skill:
        return await Skill.get(id=run.skill_id)

    async def save_inputs(
            self, run_id: str, user: User, fields: dict
    ) -> SkillRun:
        run = await self.get_run(run_id, user)
        if run.status in self.TERMINAL_STATUSES or run.status == "running":
            raise ParameterException(message="当前 Run 状态不允许修改输入")

        merged = dict(run.input_data or {})
        merged.update(fields or {})
        run.input_data = merged
        run.status = "pending"
        await run.save()

        workspace = WorkspaceService(run)
        workspace.update_meta_status("pending")
        return run

    async def save_upload(
            self,
            run_id: str,
            user: User,
            step_key: str,
            file: UploadFile,
    ) -> tuple[SkillRun, str, int]:
        run = await self.get_run(run_id, user)
        if run.status in self.TERMINAL_STATUSES or run.status == "running":
            raise ParameterException(message="当前 Run 状态不允许上传")

        skill = await self._get_skill(run)
        steps = (skill.input_schema or {}).get("wizard_steps") or []
        step = next((s for s in steps if s.get("key") == step_key), None)
        if not step:
            raise ParameterException(message=f"未找到 Wizard 步骤: {step_key}")
        if step.get("type") not in {"file", "dir"}:
            raise ParameterException(message=f"步骤 {step_key} 不支持文件上传")

        content = await file.read()
        filename = file.filename or step_key
        workspace = WorkspaceService(run)
        rel_path = workspace.step_target_path(
            step, skill.input_schema, filename=filename
        )
        workspace.save_upload(rel_path, content)

        run.status = "pending"
        await run.save()
        workspace.update_meta_status("pending")
        return run, rel_path, len(content)

    async def validate_run(self, run_id: str, user: User) -> dict:
        run = await self.get_run(run_id, user)
        skill = await self._get_skill(run)
        workspace = WorkspaceService(run)
        valid, missing = validate_run_inputs(
            workspace, skill.input_schema, run.input_data
        )
        if valid:
            run.status = "validated"
            await run.save()
            workspace.update_meta_status("validated")
        else:
            if run.status == "validated":
                run.status = "pending"
                await run.save()
                workspace.update_meta_status("pending")
        return {
            "valid": valid,
            "missing_fields": missing,
            "status": run.status,
        }

    async def get_outputs(self, run_id: str, user: User) -> list:
        run = await self.get_run(run_id, user)
        workspace = WorkspaceService(run)
        skill = await self._get_skill(run)
        _, output_root = workspace.layout_roots(skill.input_schema)
        output_dir = workspace.resolve_safe_path(output_root)
        return list_output_files(output_dir)

    async def start_run(
            self,
            run_id: str,
            user: User,
            question: Optional[str] = None,
    ) -> tuple[SkillRun, str, bool]:
        """启动 Run：wizard 进程内 SSE；async_job 投递 Celery。"""
        run = await self.get_run(run_id, user)
        if run.status in self.TERMINAL_STATUSES:
            raise ParameterException(message="Run 已结束，无法再次启动")
        if run.status == "running" or SkillRunEventHub.is_running(run_id):
            raise ParameterException(message="Run 正在执行中")

        validation = await self.validate_run(run_id, user)
        if not validation.get("valid"):
            missing = validation.get("missing_fields") or []
            labels = ", ".join(m.get("label") or m.get("key") or "?" for m in missing[:3])
            raise ParameterException(message=f"输入校验未通过：{labels}")

        skill = await self._get_skill(run)
        workspace = WorkspaceService(run)
        snapshot_version = workspace.ensure_skill_snapshot(skill.skill_key)
        run.skill_version = snapshot_version
        await run.save()

        mode = (run.interaction_mode or "wizard").lower()
        if mode == "async_job":
            run.status = "running"
            await run.save()
            workspace.update_meta_status("running")
            from backend.celery_scheduler.tasks.task_run_skill import (
                execute_skill_run_async,
            )
            execute_skill_run_async.delay(run.id, user.id, question)
            return run, mode, True

        asyncio.create_task(
            execute_skill_run(run.id, user.id, question, publish_events=True)
        )
        return run, mode, False

    async def cancel_run(self, run_id: str, user: User) -> SkillRun:
        run = await self.get_run(run_id, user)
        if run.status in self.TERMINAL_STATUSES:
            raise ParameterException(message="Run 已结束")
        SkillRunEventHub.request_cancel(run_id)
        if run.status == "running" or SkillRunEventHub.is_running(run_id):
            run.status = "cancelled"
            await run.save()
            WorkspaceService(run).update_meta_status("cancelled")
        elif run.status in self.DRAFT_STATUSES:
            run.status = "cancelled"
            await run.save()
            WorkspaceService(run).remove_workspace()
        return run

    async def retry_run(self, run_id: str, user: User) -> tuple[SkillRun, bool]:
        """基于已结束的 Run 创建新 Run，并复制输入与工作区文件。"""
        old_run = await self.get_run(run_id, user)
        if old_run.status not in self.TERMINAL_STATUSES:
            raise ParameterException(message="仅已结束的 Run 可重试")

        skill = await self._load_skill_for_run(old_run.skill_id, user)
        new_run = await self.create(
            {
                "user_id": user.id,
                "skill_id": skill.id,
                "skill_key": skill.skill_key,
                "skill_version": skill.skill_version,
                "interaction_mode": skill.interaction_mode,
                "conversation_id": old_run.conversation_id,
                "model_config_id": old_run.model_config_id,
                "knowledge_base_ids": old_run.knowledge_base_ids,
                "input_data": dict(old_run.input_data or {}),
                "status": "pending",
            }
        )

        new_ws = WorkspaceService(new_run)
        new_ws.init_draft_workspace(skill_version=skill.skill_version or "")
        old_ws = WorkspaceService(old_run)
        new_ws.copy_inputs_from(old_ws, skill.input_schema)

        validation = await self.validate_run(new_run.id, user)
        return new_run, bool(validation.get("valid"))

    async def delete_run(self, run_id: str, user: User) -> None:
        run = await self.get_run(run_id, user)
        if run.status == "running" or SkillRunEventHub.is_running(run_id):
            raise ParameterException(message="执行中的 Run 无法删除，请先取消")
        WorkspaceService(run).remove_workspace()
        await self.soft_delete(run_id)

    async def cleanup_runs(
            self,
            user: User,
            *,
            days: Optional[int] = None,
            dry_run: bool = False,
    ) -> dict:
        retention_days = days or PROJECT_CONFIG.SKILL_RUN_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        qs = self.model.filter(
            user_id=user.id,
            state__not=1,
            status__in=list(self.TERMINAL_STATUSES),
            updated_time__lt=cutoff,
        )
        runs = await qs.all()
        scanned = len(runs)
        deleted = 0
        if dry_run:
            return {
                "scanned": scanned,
                "deleted": 0,
                "dry_run": True,
                "retention_days": retention_days,
            }

        for run in runs:
            if SkillRunEventHub.is_running(run.id):
                continue
            WorkspaceService(run).remove_workspace()
            await self.soft_delete(run.id)
            deleted += 1

        return {
            "scanned": scanned,
            "deleted": deleted,
            "dry_run": False,
            "retention_days": retention_days,
        }

    async def cleanup_stale_drafts(
            self,
            user: User,
            *,
            days: Optional[int] = None,
            dry_run: bool = False,
    ) -> dict:
        """清理超过 N 天仍未 start 的 draft Run（pending/validated）。"""
        stale_days = days or PROJECT_CONFIG.SKILL_DRAFT_STALE_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        qs = self.model.filter(
            user_id=user.id,
            state__not=1,
            status__in=list(self.DRAFT_STATUSES),
            created_time__lt=cutoff,
        )
        runs = await qs.all()
        scanned = len(runs)
        if dry_run:
            return {
                "scanned": scanned,
                "deleted": 0,
                "dry_run": True,
                "stale_days": stale_days,
            }

        deleted = 0
        for run in runs:
            if SkillRunEventHub.is_running(run.id):
                continue
            WorkspaceService(run).remove_workspace()
            run.status = "cancelled"
            await run.save()
            await self.soft_delete(run.id)
            deleted += 1

        return {
            "scanned": scanned,
            "deleted": deleted,
            "dry_run": False,
            "stale_days": stale_days,
        }

    def run_to_out(self, run: SkillRun, skill: Optional[Skill] = None) -> dict:
        skill_name = None
        if skill:
            skill_name = skill.name
        elif getattr(run, "skill", None):
            skill_name = run.skill.name
        data = {
            "id": run.id,
            "status": run.status,
            "skill_id": run.skill_id,
            "skill_key": run.skill_key,
            "skill_version": run.skill_version,
            "interaction_mode": run.interaction_mode,
            "conversation_id": run.conversation_id,
            "model_config_id": run.model_config_id,
            "knowledge_base_ids": run.knowledge_base_ids,
            "input_data": run.input_data,
            "error_message": run.error_message,
            "created_time": run.created_time,
            "updated_time": run.updated_time,
            "skill_name": skill_name,
        }
        return data
