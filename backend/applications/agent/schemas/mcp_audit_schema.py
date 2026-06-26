# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class McpAuditLogOut(BaseModel):
    id: str
    user_id: int
    username: str
    conversation_id: Optional[str] = None
    message_id: Optional[int] = None
    skill_id: Optional[str] = None
    skill_run_id: Optional[str] = None
    mcp_server_id: str
    server_name: str
    transport: str
    event_type: str
    tool_name: str
    status: str
    arguments_json: Optional[str] = None
    result_preview: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    trace_id: Optional[str] = None
    created_time: datetime

    model_config = ConfigDict(from_attributes=True)


class McpAuditLogSelect(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    mcp_server_id: Optional[str] = None
    tool_name: Optional[str] = None
    status: Optional[str] = None
    event_type: Optional[str] = None
    conversation_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    order: Optional[List[str]] = Field(default_factory=lambda: ["-created_time"])
