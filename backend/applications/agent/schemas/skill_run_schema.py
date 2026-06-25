# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_schema.py
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SkillRunStatus = Literal[
    "pending", "validated", "running", "completed", "failed", "cancelled"
]


class SkillRunCreate(BaseModel):
    skill_id: str = Field(..., description="技能 ID")
    conversation_id: Optional[str] = Field(default=None, description="对话 ID")
    model_config_id: Optional[str] = Field(default=None, description="模型配置 ID")
    knowledge_base_ids: Optional[list[str]] = Field(
        default=None, description="知识库 ID 列表"
    )


class SkillRunInputsUpdate(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict, description="文本/选择类字段")


class SkillRunValidateResult(BaseModel):
    valid: bool = Field(..., description="是否通过校验")
    missing_fields: list[dict[str, Any]] = Field(default_factory=list)
    status: str = Field(default="pending", description="Run 状态")


class SkillRunOut(BaseModel):
    id: str
    status: str
    skill_id: str
    skill_key: str
    skill_version: Optional[str] = None
    interaction_mode: str
    conversation_id: Optional[str] = None
    model_config_id: Optional[str] = None
    knowledge_base_ids: Optional[list[str]] = None
    input_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_time: datetime
    updated_time: datetime
    skill_name: Optional[str] = Field(default=None, description="技能名称")

    model_config = ConfigDict(from_attributes=True)


class SkillRunSearchQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    skill_id: Optional[str] = None
    status: Optional[str] = None
    conversation_id: Optional[str] = None


class SkillRunFileUploadResult(BaseModel):
    key: str
    path: str
    size: int


class SkillRunStart(BaseModel):
    question: Optional[str] = Field(default=None, description="执行任务描述/问题")


class SkillRunStartResult(BaseModel):
    run_id: str
    status: str
    mode: str = Field(description="wizard 或 async_job")
    async_execution: bool = False
    execution_message_id: Optional[int] = Field(
        default=None, description="独立模型执行回复消息 ID"
    )


class SkillRunRetryResult(BaseModel):
    new_run_id: str
    source_run_id: str
    status: str
    valid: bool = Field(default=False, description="输入是否已通过校验")


class SkillRunCleanupQuery(BaseModel):
    days: Optional[int] = Field(default=None, ge=1, le=365, description="保留天数")
    dry_run: bool = Field(default=False, description="仅预览不删除")


class SkillRunCleanupResult(BaseModel):
    scanned: int = 0
    deleted: int = 0
    dry_run: bool = False
    retention_days: int = 30


class SkillStaleDraftCleanupQuery(BaseModel):
    days: Optional[int] = Field(default=None, ge=1, le=365, description="未 start 超过天数")
    dry_run: bool = Field(default=False, description="仅预览不删除")


class SkillStaleDraftCleanupResult(BaseModel):
    scanned: int = 0
    deleted: int = 0
    dry_run: bool = False
    stale_days: int = 1
