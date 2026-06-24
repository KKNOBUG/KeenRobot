# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : agent_crud.py
"""
from typing import List, Optional

from fastapi import UploadFile

from backend.applications.agent.models.agent_model import McpServer, Skill
from backend.applications.agent.schemas.agent_schema import (
    McpServerCreate,
    McpServerUpdate,
    SkillCreate,
    SkillUpdate,
)
from backend.applications.agent.services.skill_registry import (
    install_skill_from_zip,
    list_disk_skills,
    read_skill_preview,
)
from backend.applications.agent.services.skill_validation import (
    validate_embedded_mcp_access,
    validate_interaction_mode,
    validate_skill_enable,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.user.models.user_model import User
from backend.core.exceptions import NotFoundException, ParameterException


class SkillCrud(ScaffoldCrud):
    def __init__(self):
        super().__init__(model=Skill)

    async def list_by_user(
        self, user_id: int, *, search: str = None, manage: bool = False
    ) -> List[Skill]:
        """查询技能列表；manage=True 时包含已禁用项（聊天选择器仅返回启用项）"""
        qs = self.model.filter(user_id=user_id, state__not=1)
        if not manage:
            qs = qs.filter(is_enabled=True)
        if search:
            qs = qs.filter(name__icontains=search)
        return await qs.order_by("-updated_time")

    async def get_by_id(self, skill_id: str) -> Optional[Skill]:
        return await self.model.get_or_none(id=skill_id, state__not=1)

    async def get_skill(self, skill_id: str, user: User) -> Skill:
        skill = await self.get_by_id(skill_id)
        if not skill:
            raise NotFoundException(message="技能不存在")
        self.check_access(skill, user)
        return skill

    def check_access(self, skill: Skill, user: User) -> None:
        if skill.user_id != user.id:
            raise NotFoundException(message="技能不存在")

    async def create_skill(self, user: User, data: SkillCreate) -> Skill:
        obj_dict = data.create_dict()
        obj_dict["user_id"] = user.id
        return await self.create(obj_dict)

    async def update_skill(
        self, skill_id: str, user: User, data: SkillUpdate
    ) -> Skill:
        effective_id = data.skill_id or skill_id
        skill = await self.get_skill(effective_id, user)
        obj_dict = data.model_dump(exclude_unset=True, exclude={"skill_id"})

        if "interaction_mode" in obj_dict and obj_dict["interaction_mode"] is not None:
            obj_dict["interaction_mode"] = validate_interaction_mode(
                obj_dict["interaction_mode"]
            )

        next_enabled = obj_dict.get("is_enabled", skill.is_enabled)
        next_mode = obj_dict.get("interaction_mode", skill.interaction_mode)
        next_schema = obj_dict.get("input_schema", skill.input_schema)
        validate_skill_enable(
            interaction_mode=next_mode,
            input_schema=next_schema,
            is_enabled=next_enabled,
        )

        next_execution = obj_dict.get("execution", skill.execution)
        if "execution" in obj_dict or next_enabled:
            await validate_embedded_mcp_access(next_execution, user)

        if obj_dict:
            skill = skill.update_from_dict(obj_dict)
            await skill.save()
        return skill

    async def sync_skills_for_user(self, user: User) -> tuple[int, int, int, List[Skill]]:
        """磁盘 Skill → DB，仅更新内容元数据。"""
        disk_skills = list_disk_skills()
        disk_keys = {item.skill_key for item in disk_skills}
        created = updated = removed = 0

        existing = await self.model.filter(user_id=user.id, state__not=1).all()
        by_key = {
            s.skill_key: s for s in existing if s.skill_key
        }

        synced: List[Skill] = []
        for meta in disk_skills:
            skill = by_key.get(meta.skill_key)
            if not skill:
                skill = await self.create(
                    {
                        "user_id": user.id,
                        "skill_key": meta.skill_key,
                        "source": "filesystem",
                        "name": meta.name,
                        "description": meta.description,
                        "skill_version": meta.skill_version,
                        "interaction_mode": "chat",
                        "is_enabled": False,
                    }
                )
                created += 1
            else:
                skill.name = meta.name
                skill.description = meta.description
                skill.skill_version = meta.skill_version
                await skill.save()
                updated += 1
            synced.append(skill)

        for skill in existing:
            if skill.skill_key and skill.skill_key not in disk_keys:
                skill.state = 1
                await skill.save()
                removed += 1

        synced.sort(key=lambda s: s.name.lower())
        return created, updated, removed, synced

    async def upload_skill_zip(
            self,
            user: User,
            file: UploadFile,
            *,
            skill_key: Optional[str] = None,
            overwrite: bool = False,
    ) -> dict:
        from backend.applications.agent.services.skill_registry import get_skills_root

        content = await file.read()
        guess_key = skill_key
        if not guess_key and file.filename:
            import os
            base = os.path.splitext(os.path.basename(file.filename))[0]
            if base:
                guess_key = base
        existed = bool(guess_key and (get_skills_root() / guess_key).exists())

        meta = install_skill_from_zip(
            content,
            skill_key=guess_key,
            overwrite=overwrite,
        )
        await self.sync_skills_for_user(user)
        return {
            "skill_key": meta.skill_key,
            "name": meta.name,
            "skill_version": meta.skill_version,
            "overwritten": overwrite and existed,
        }

    async def get_skill_preview(self, skill_id: str, user: User) -> dict:
        skill = await self.get_skill(skill_id, user)
        if not skill.skill_key:
            raise ParameterException(message="该技能未关联磁盘 Skill，请先同步")
        try:
            return read_skill_preview(skill.skill_key)
        except FileNotFoundError as exc:
            raise NotFoundException(message=str(exc)) from exc

    async def delete_skill(self, skill_id: str, user: User) -> None:
        skill = await self.get_skill(skill_id, user)
        skill.state = 1
        await skill.save()


class McpServerCrud(ScaffoldCrud):
    def __init__(self):
        super().__init__(model=McpServer)

    async def list_by_user(
        self, user_id: int, *, search: str = None, manage: bool = False
    ) -> List[McpServer]:
        qs = self.model.filter(user_id=user_id, state__not=1)
        if not manage:
            qs = qs.filter(is_enabled=True)
        if search:
            qs = qs.filter(name__icontains=search)
        return await qs.order_by("-updated_time")

    async def get_by_id(self, mcp_id: str) -> Optional[McpServer]:
        return await self.model.get_or_none(id=mcp_id, state__not=1)

    async def get_mcp_server(self, mcp_id: str, user: User) -> McpServer:
        mcp = await self.get_by_id(mcp_id)
        if not mcp:
            raise NotFoundException(message="MCP 服务不存在")
        self.check_access(mcp, user)
        return mcp

    def check_access(self, mcp: McpServer, user: User) -> None:
        if mcp.user_id != user.id:
            raise NotFoundException(message="MCP 服务不存在")

    async def create_mcp_server(self, user: User, data: McpServerCreate) -> McpServer:
        obj_dict = data.create_dict()
        obj_dict["user_id"] = user.id
        return await self.create(obj_dict)

    async def update_mcp_server(
        self, mcp_id: str, user: User, data: McpServerUpdate
    ) -> McpServer:
        effective_id = data.mcp_id or mcp_id
        mcp = await self.get_mcp_server(effective_id, user)
        obj_dict = data.model_dump(exclude_unset=True, exclude={"mcp_id"})
        if obj_dict:
            mcp = mcp.update_from_dict(obj_dict)
            await mcp.save()
        return mcp

    async def delete_mcp_server(self, mcp_id: str, user: User) -> None:
        mcp = await self.get_mcp_server(mcp_id, user)
        mcp.state = 1
        await mcp.save()

    async def refresh_tools(self, mcp_id: str, user: User) -> McpServer:
        from backend.applications.agent.services.mcp_tools import refresh_mcp_tools

        mcp = await self.get_mcp_server(mcp_id, user)
        tools = await refresh_mcp_tools(mcp.transport, mcp.config)
        config = dict(mcp.config or {})
        config["tools"] = tools
        mcp.config = config
        await mcp.save()
        return mcp
