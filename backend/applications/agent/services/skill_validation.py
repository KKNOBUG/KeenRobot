# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_validation.py
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.core.exceptions import ParameterException

if TYPE_CHECKING:
    from backend.applications.user.models.user_model import User

INTERACTION_MODES = frozenset({"chat", "wizard", "async_job"})
WIZARD_STEP_TYPES = frozenset({"file", "dir", "text", "choice", "confirm"})


def validate_input_schema(input_schema: Optional[Dict[str, Any]]) -> None:
    """校验 input_schema JSON 契约。"""
    if input_schema is None:
        raise ParameterException(message="input_schema 不能为空")
    if not isinstance(input_schema, dict):
        raise ParameterException(message="input_schema 必须是 JSON 对象")

    steps = input_schema.get("wizard_steps")
    if not isinstance(steps, list) or not steps:
        raise ParameterException(message="input_schema.wizard_steps 必须是非空数组")

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ParameterException(message=f"wizard_steps[{idx}] 必须是对象")
        step_type = step.get("type")
        if step_type not in WIZARD_STEP_TYPES:
            raise ParameterException(
                message=f"wizard_steps[{idx}].type 无效: {step_type}"
            )
        if not step.get("key"):
            raise ParameterException(message=f"wizard_steps[{idx}].key 不能为空")


def validate_skill_enable(
        *,
        interaction_mode: str,
        input_schema: Optional[Dict[str, Any]],
        is_enabled: bool,
) -> None:
    """启用门禁：wizard/async_job 必须配置合法 input_schema。"""
    if not is_enabled:
        return
    mode = (interaction_mode or "chat").lower()
    if mode in {"wizard", "async_job"}:
        validate_input_schema(input_schema)


def validate_interaction_mode(mode: Optional[str]) -> str:
    value = (mode or "chat").lower()
    if value not in INTERACTION_MODES:
        raise ParameterException(
            message=f"interaction_mode 无效，可选: {', '.join(sorted(INTERACTION_MODES))}"
        )
    return value


def resolve_embedded_mcp_ids(execution: Optional[Dict[str, Any]]) -> List[str]:
    """从 Skill.execution 解析内嵌 MCP 服务 ID 列表。"""
    if not execution or not isinstance(execution, dict):
        return []
    raw = execution.get("mcp_ids")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ParameterException(message="execution.mcp_ids 必须是字符串数组")
    ids: List[str] = []
    for item in raw:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            ids.append(text)
    return ids


async def validate_embedded_mcp_access(
        execution: Optional[Dict[str, Any]],
        user: "User",
) -> None:
    """校验 Skill 内嵌 MCP 归属与可用性。"""
    mcp_ids = resolve_embedded_mcp_ids(execution)
    if not mcp_ids:
        return

    from backend.applications.agent.services.agent_crud import McpServerCrud

    crud = McpServerCrud()
    for mcp_id in mcp_ids:
        server = await crud.get_mcp_server(mcp_id, user)
        if not server.is_enabled:
            raise ParameterException(message=f"MCP 服务「{server.name}」未启用，无法绑定到 Skill")
        tools = (server.config or {}).get("tools") or []
        if not tools:
            raise ParameterException(
                message=f"MCP 服务「{server.name}」尚未刷新工具列表，请先在 MCP 管理中点击「刷新」"
            )
