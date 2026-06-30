# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : agent_model.py
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    StateModel,
    TimestampMixin,
    unique_identify,
)


class Skill(ScaffoldModel, StateModel, TimestampMixin):
    """Agent 技能定义"""
    id = fields.CharField(
        default=unique_identify, max_length=64, primary_key=True, description="技能ID"
    )
    skill_key = fields.CharField(
        max_length=128, null=True, description="磁盘 Skill 目录名"
    )
    source = fields.CharField(
        max_length=32, default="filesystem", description="来源(filesystem/custom)"
    )
    name = fields.CharField(max_length=128, description="技能名称")
    description = fields.TextField(null=True, description="技能描述")
    skill_version = fields.CharField(
        max_length=64, null=True, description="磁盘 Skill 包版本"
    )
    interaction_mode = fields.CharField(
        max_length=32, default="chat", description="交互模式(chat/wizard/async_job)"
    )
    input_schema = fields.JSONField(null=True, description="Wizard 输入 schema")
    execution = fields.JSONField(null=True, description="执行偏好配置")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="skills",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    is_enabled = fields.BooleanField(default=True, description="是否启用")
    config = fields.JSONField(null=True, description="技能配置(扩展字段)")

    class Meta:
        table = "keenrobot_skills"
        unique_together = (("user_id", "skill_key"),)


class McpServer(ScaffoldModel, StateModel, TimestampMixin):
    """MCP 服务配置"""
    id = fields.CharField(
        default=unique_identify, max_length=64, primary_key=True, description="MCP服务ID"
    )
    name = fields.CharField(max_length=128, description="服务名称")
    description = fields.TextField(null=True, description="服务描述")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="mcp_servers",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    is_enabled = fields.BooleanField(default=True, description="是否启用")
    transport = fields.CharField(
        max_length=32, default="stdio", description="传输方式(stdio/sse/http)"
    )
    config = fields.JSONField(null=True, description="连接配置")

    class Meta:
        table = "keenrobot_mcp_servers"


class SkillRun(ScaffoldModel, StateModel, TimestampMixin):
    """Skill 执行任务"""
    id = fields.CharField(
        default=unique_identify, max_length=64, primary_key=True, description="Run ID"
    )
    status = fields.CharField(
        max_length=32,
        default="pending",
        description="pending/validated/running/completed/failed/cancelled",
    )
    skill = fields.ForeignKeyField(
        "models.Skill",
        related_name="runs",
        on_delete=fields.CASCADE,
        description="关联技能",
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="skill_runs",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    conversation_id = fields.CharField(
        max_length=64, null=True, description="关联对话 ID"
    )
    model_config_id = fields.CharField(
        max_length=64, null=True, description="模型配置 ID"
    )
    skill_key = fields.CharField(max_length=128, description="快照 Skill Key")
    skill_version = fields.CharField(max_length=64, null=True, description="快照版本")
    interaction_mode = fields.CharField(
        max_length=32, description="执行时交互模式"
    )
    knowledge_base_ids = fields.JSONField(null=True, description="关联知识库")
    input_data = fields.JSONField(null=True, description="Wizard 文本/选择类输入")
    error_message = fields.TextField(null=True, description="错误信息")

    class Meta:
        table = "keenrobot_skill_runs"
