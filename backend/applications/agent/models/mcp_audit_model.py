# -*- coding: utf-8 -*-
from tortoise import fields

from backend.applications.base.services.scaffold import ScaffoldModel, TimestampMixin, unique_identify


class McpAuditLog(ScaffoldModel, TimestampMixin):
    """MCP 工具级审计：call_tool / sampling 等（不含 HTTP refresh/sync，走 keenrobot_audit）。"""

    id = fields.CharField(
        default=unique_identify, max_length=64, pk=True, description="审计ID"
    )
    user_id = fields.BigIntField(index=True, description="用户ID")
    username = fields.CharField(max_length=64, default="", description="用户名")
    conversation_id = fields.CharField(max_length=64, null=True, index=True, description="对话ID")
    message_id = fields.IntField(null=True, description="消息ID")
    skill_id = fields.CharField(max_length=64, null=True, index=True, description="技能ID")
    skill_run_id = fields.CharField(max_length=64, null=True, index=True, description="SkillRun ID")
    mcp_server_id = fields.CharField(max_length=64, index=True, description="MCP服务ID")
    server_name = fields.CharField(max_length=128, description="MCP服务名")
    transport = fields.CharField(max_length=32, default="stdio", description="传输方式")
    event_type = fields.CharField(max_length=32, index=True, description="tool_call|sampling|resource_read")
    tool_name = fields.CharField(max_length=128, index=True, description="工具或协议方法名")
    status = fields.CharField(max_length=16, index=True, description="done|error|cancelled")
    arguments_json = fields.TextField(null=True, description="参数 JSON（脱敏截断）")
    result_preview = fields.TextField(null=True, description="结果摘要")
    error_message = fields.CharField(max_length=512, null=True, description="错误信息")
    duration_ms = fields.IntField(null=True, description="耗时毫秒")
    trace_id = fields.CharField(max_length=64, null=True, index=True, description="Trace ID")

    class Meta:
        table = "keenrobot_mcp_audit"
        ordering = ["-created_time"]
