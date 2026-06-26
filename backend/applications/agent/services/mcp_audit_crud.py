# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple

from tortoise.expressions import Q

from backend.applications.agent.models.mcp_audit_model import McpAuditLog
from backend.applications.agent.schemas.mcp_audit_schema import McpAuditLogSelect
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.user.models.user_model import User


class McpAuditCrud(ScaffoldCrud):
    def __init__(self):
        super().__init__(model=McpAuditLog)

    def _user_scope(self, user: User) -> Q:
        if user.is_superuser:
            return Q()
        return Q(user_id=user.id)

    async def list_logs(
            self,
            user: User,
            query: McpAuditLogSelect,
    ) -> Tuple[int, List[McpAuditLog]]:
        q = self._user_scope(user)
        if query.mcp_server_id:
            q &= Q(mcp_server_id=query.mcp_server_id)
        if query.tool_name:
            q &= Q(tool_name__icontains=query.tool_name)
        if query.status:
            q &= Q(status=query.status)
        if query.event_type:
            q &= Q(event_type=query.event_type)
        if query.conversation_id:
            q &= Q(conversation_id=query.conversation_id)
        if query.start_time and query.end_time:
            q &= Q(created_time__range=[query.start_time, query.end_time])
        elif query.start_time:
            q &= Q(created_time__gte=query.start_time)
        elif query.end_time:
            q &= Q(created_time__lte=query.end_time)
        return await self.list(
            page=query.page,
            page_size=query.page_size,
            search=q,
            order=query.order,
        )
