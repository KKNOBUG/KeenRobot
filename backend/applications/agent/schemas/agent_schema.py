# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : agent_schema.py
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


InteractionMode = Literal["chat", "wizard", "async_job"]
SkillSource = Literal["filesystem", "custom"]


class SkillBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128, description="技能名称")
    description: Optional[str] = Field(default=None, description="技能描述")
    is_enabled: Optional[bool] = Field(default=None, description="是否启用")
    interaction_mode: Optional[InteractionMode] = Field(
        default=None, description="交互模式"
    )
    input_schema: Optional[dict[str, Any]] = Field(
        default=None, description="Wizard 输入 schema"
    )
    execution: Optional[dict[str, Any]] = Field(
        default=None, description="执行偏好"
    )
    config: Optional[dict[str, Any]] = Field(default=None, description="扩展配置")


class SkillCreate(SkillBase):
    name: str = Field(..., min_length=1, max_length=128, description="技能名称")
    is_enabled: bool = Field(default=True, description="是否启用")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class SkillUpdate(SkillBase):
    skill_id: Optional[str] = Field(default=None, description="技能ID")


class SkillOut(BaseModel):
    id: str = Field(..., description="技能ID")
    skill_key: Optional[str] = Field(default=None, description="磁盘 Skill 目录名")
    source: str = Field(default="filesystem", description="来源")
    name: str = Field(..., description="技能名称")
    description: Optional[str] = Field(default=None, description="技能描述")
    skill_version: Optional[str] = Field(default=None, description="磁盘版本")
    interaction_mode: str = Field(default="chat", description="交互模式")
    input_schema: Optional[dict[str, Any]] = Field(default=None, description="Wizard schema")
    execution: Optional[dict[str, Any]] = Field(default=None, description="执行偏好")
    is_enabled: bool = Field(default=True, description="是否启用")
    config: Optional[dict[str, Any]] = Field(default=None, description="扩展配置")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class SkillSyncResult(BaseModel):
    created: int = Field(default=0, description="新增数量")
    updated: int = Field(default=0, description="更新数量")
    removed: int = Field(default=0, description="移除数量")
    skills: list[SkillOut] = Field(default_factory=list, description="同步后列表")


class SkillUploadResult(BaseModel):
    skill_key: str
    name: str
    skill_version: str
    overwritten: bool = False


class SkillPreviewOut(BaseModel):
    skill_key: str
    skill_md: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_preview: str = ""
    directory_tree: list[dict[str, Any]] = Field(default_factory=list)
    skill_version: str = ""


class McpServerBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128, description="服务名称")
    description: Optional[str] = Field(default=None, description="服务描述")
    is_enabled: Optional[bool] = Field(default=None, description="是否启用")
    transport: Optional[Literal["stdio", "sse", "http"]] = Field(
        default=None, description="传输方式"
    )
    config: Optional[dict[str, Any]] = Field(default=None, description="连接配置")


class McpServerCreate(McpServerBase):
    name: str = Field(..., min_length=1, max_length=128, description="服务名称")
    is_enabled: bool = Field(default=True, description="是否启用")
    transport: Literal["stdio", "sse", "http"] = Field(
        default="stdio", description="传输方式"
    )

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class McpServerUpdate(McpServerBase):
    mcp_id: Optional[str] = Field(default=None, description="MCP服务ID")


class McpServerOut(BaseModel):
    id: str = Field(..., description="MCP服务ID")
    name: str = Field(..., description="服务名称")
    description: Optional[str] = Field(default=None, description="服务描述")
    is_enabled: bool = Field(default=True, description="是否启用")
    transport: str = Field(default="stdio", description="传输方式")
    config: Optional[dict[str, Any]] = Field(default=None, description="连接配置")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)
