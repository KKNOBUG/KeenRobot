# -*- coding: utf-8
"""M2 用户记忆 API Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserMemoryOut(BaseModel):
    id: str
    memory_key: Optional[str] = None
    content: str
    source: str = "explicit"
    expires_at: Optional[datetime] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserMemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=200, description="记忆正文")
    memory_key: Optional[str] = Field(default=None, max_length=64, description="可选分类")
