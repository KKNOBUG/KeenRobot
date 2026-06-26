# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : conversation_crud.py
@DateTime: 2026/6/9
"""
from typing import AsyncIterator, List, Optional, Dict, Any

from tortoise.query_utils import Prefetch

from backend.applications.agent.schemas.skill_run_schema import SkillRunCreate
from backend.applications.agent.services.agent_crud import McpServerCrud, SkillCrud
from backend.applications.agent.services.skill_run_crud import SkillRunCrud
from backend.applications.base.rag.chain import rag_stream
from backend.applications.mcp.orchestrator import MCP_AGENT_SYSTEM_PROMPT, McpAgentOrchestrator
from backend.applications.base.rag.skill_agent import skill_agent_stream
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.conversation.models.conversation_model import Conversation, Message
from backend.applications.conversation.schemas.conversation_schema import (
    ChatRequest,
    ConversationBrief,
    ConversationCreate,
    ConversationBindingsUpdate,
    ConversationStatOut,
    ConversationUpdate,
    KnowledgeBaseBrief,
    MessageCreate,
    MessageUpdate,
    ModelConfigBrief,
    SkillIntakeStartResult,
    SkillIntakeUpdate,
    TokenUsage,
    UserBrief,
)
from backend.applications.conversation.services.binding_utils import (
    ResolvedConversationBindings,
    kb_ids_from_conversation,
    mcp_ids_from_conversation,
    skill_ids_from_conversation,
)
from backend.applications.conversation.services.skill_intake_helpers import (
    freeze_intake_as_submitted,
)
from backend.applications.knowledge_base.models.knowledge_base_model import KnowledgeBase
from backend.applications.knowledge_base.services.knowledge_base_crud import KnowledgeBaseCrud
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.services.llm_connection import (
    resolve_chat_llm_params,
    resolve_effective_enable_thinking,
)
from backend.applications.model_config.services.model_config_crud import ModelConfigCrud
from backend.applications.user.models.user_model import User
from backend.core.exceptions import NotFoundException, ParameterException
from backend.enums.chat_session_enum import ChatMessageRole

_mcp_orchestrator = McpAgentOrchestrator()


class MessageCrud(ScaffoldCrud[Message, MessageCreate, MessageUpdate]):
    def __init__(self):
        super().__init__(model=Message)

    async def list_by_conversation(self, conversation_id: str) -> List[Message]:
        """获取对话下的消息列表（排除已禁用）"""
        return await self.model.filter(
            conversation_id=conversation_id, state__not=1
        ).order_by("created_time")

    async def add_message(
            self,
            conversation_id: str,
            role: ChatMessageRole,
            content: str,
            *,
            prompt_tokens: Optional[int] = None,
            completion_tokens: Optional[int] = None,
            reasoning_tokens: Optional[int] = None,
            process_trace: Optional[List[dict]] = None,
            skill_run_ref: Optional[dict] = None,
            skill_intake: Optional[dict] = None,
    ) -> Message:
        """添加消息"""
        data = MessageCreate(
            conversation_id=conversation_id,
            role=role,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            process_trace=process_trace,
            skill_run_ref=skill_run_ref,
            skill_intake=skill_intake,
        )
        return await self.create(data.create_dict())

    async def find_intake_message(
            self, conversation_id: str, run_id: str
    ) -> Optional[Message]:
        messages = await self.model.filter(
            conversation_id=conversation_id,
            state__not=1,
        ).order_by("-created_time")
        for message in messages:
            intake = message.skill_intake or {}
            if intake.get("run_id") == run_id:
                return message
        return None

    async def find_execution_message(
            self, conversation_id: str, run_id: str
    ) -> Optional[Message]:
        messages = await self.model.filter(
            conversation_id=conversation_id,
            state__not=1,
        ).order_by("-created_time")
        for message in messages:
            ref = message.skill_run_ref or {}
            if ref.get("run_id") == run_id:
                return message
        return None

    async def update_skill_intake(
            self,
            message_id: int,
            conversation_id: str,
            data: SkillIntakeUpdate,
    ) -> Message:
        message = await self.model.get_or_none(
            id=message_id,
            conversation_id=conversation_id,
            state__not=1,
        )
        if not message:
            raise NotFoundException(message="消息不存在")

        intake = dict(message.skill_intake or {})
        payload = data.model_dump(exclude_unset=True)
        intake_fields = (
            "phase",
            "step_index",
            "form_values",
            "file_labels",
            "missing_fields",
            "run_summary",
            "process_trace",
        )
        for key in intake_fields:
            if key in payload and payload[key] is not None:
                intake[key] = payload[key]
        message.skill_intake = intake

        if payload.get("content") is not None:
            message.content = payload["content"]
        if payload.get("process_trace") is not None:
            message.process_trace = payload["process_trace"]
        if payload.get("skill_run_ref") is not None:
            message.skill_run_ref = payload["skill_run_ref"]
        await message.save()
        return message

    async def soft_delete_by_conversations(self, conversation_ids: List[str]) -> None:
        """批量软删除对话下的消息"""
        if conversation_ids:
            await self.model.filter(
                conversation_id__in=conversation_ids, state__not=1
            ).update(state=1)


class ConversationCrud(ScaffoldCrud[Conversation, ConversationCreate, ConversationUpdate]):
    def __init__(self):
        super().__init__(model=Conversation)
        self.message = MessageCrud()

    async def list_by_user(self, user_id: int) -> List[Conversation]:
        """获取用户的对话列表（排除已禁用）"""
        return await self.model.filter(
            user_id=user_id, state__not=1
        ).order_by("-updated_time")

    async def get_by_id(
            self, conversation_id: str, user_id: int
    ) -> Optional[Conversation]:
        """根据 ID 和用户 ID 获取对话（排除已禁用）"""
        return await self.model.get_or_none(
            id=conversation_id, user_id=user_id, state__not=1
        )

    async def get_conversation(
            self, conversation_id: str, user: User
    ) -> Conversation:
        """获取对话及其消息列表；不存在则抛出 NotFoundException。"""
        conv = (
            await self.model.filter(
                id=conversation_id, user_id=user.id, state__not=1
            )
            .prefetch_related(
                Prefetch(
                    "messages",
                    Message.filter(state__not=1).order_by("created_time"),
                )
            )
            .first()
        )
        if not conv:
            raise NotFoundException(message="对话不存在")
        return conv

    async def create_for_user(self, user_id: int) -> Conversation:
        """为用户创建新对话"""
        data = ConversationCreate(user_id=user_id)
        return await self.create(data.create_dict())

    async def clear_by_user(self, user_id: int) -> None:
        """软删除用户的所有对话及消息"""
        conv_ids = await self.model.filter(
            user_id=user_id, state__not=1
        ).values_list("id", flat=True)
        if conv_ids:
            await self.message.soft_delete_by_conversations(conv_ids)
            await self.model.filter(id__in=conv_ids).update(state=1)

    async def update_meta(
            self,
            conversation: Conversation,
            *,
            knowledge_base_ids: Optional[List[str]] = None,
            skill_ids: Optional[List[str]] = None,
            mcp_ids: Optional[List[str]] = None,
            model_config_id: Optional[str] = None,
            enable_thinking: Optional[bool] = None,
            title: Optional[str] = None,
    ) -> None:
        """更新对话元数据"""
        payload: Dict[str, Any] = {}
        if knowledge_base_ids is not None:
            payload["knowledge_base_ids"] = knowledge_base_ids
        if skill_ids is not None:
            payload["skill_ids"] = skill_ids
        if mcp_ids is not None:
            payload["mcp_ids"] = mcp_ids
        if model_config_id is not None:
            payload["model_config_id"] = model_config_id
        if enable_thinking is not None:
            payload["enable_thinking"] = enable_thinking
        if title is not None:
            payload["title"] = title
        if not payload:
            return
        await self.model.filter(id=conversation.id).update(**payload)
        for key, value in payload.items():
            setattr(conversation, key, value)

    async def delete_conversation(self, conversation_id: str, user: User) -> None:
        """软删除对话及其消息"""
        conv = await self.get_by_id(conversation_id, user.id)
        if not conv:
            raise NotFoundException(message="对话不存在")
        await self.message.soft_delete_by_conversations([conv.id])
        conv.state = 1
        await conv.save()

    async def _validate_kb_access(
            self, knowledge_base_ids: List[str], user: User
    ) -> None:
        """校验知识库访问权限"""
        kb_crud = KnowledgeBaseCrud()
        for kb_id in knowledge_base_ids:
            kb = await kb_crud.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=f"知识库 {kb_id} 不存在")
            kb_crud.check_access(kb, user)

    async def _validate_skill_access(
            self, skill_ids: List[str], user: User
    ) -> None:
        """校验技能访问权限"""
        skill_crud = SkillCrud()
        for skill_id in skill_ids:
            skill = await skill_crud.get_by_id(skill_id)
            if not skill or not skill.is_enabled:
                raise NotFoundException(message=f"技能 {skill_id} 不存在")
            skill_crud.check_access(skill, user)

    async def _partition_skill_ids(
            self, skill_ids: List[str], user: User
    ) -> tuple[List[str], List[str]]:
        """按 interaction_mode 拆分为聊天 Skill 与向导 Skill。"""
        chat_ids: List[str] = []
        wizard_ids: List[str] = []
        for skill_id in skill_ids:
            skill = await SkillCrud().get_skill(skill_id, user)
            mode = (skill.interaction_mode or "chat").lower()
            if mode in ("wizard", "async_job"):
                wizard_ids.append(skill_id)
            else:
                chat_ids.append(skill_id)
        return chat_ids, wizard_ids

    async def _validate_mcp_access(
            self, mcp_ids: List[str], user: User
    ) -> None:
        """校验 MCP 服务访问权限"""
        mcp_crud = McpServerCrud()
        for mcp_id in mcp_ids:
            mcp = await mcp_crud.get_by_id(mcp_id)
            if not mcp or not mcp.is_enabled:
                raise NotFoundException(message=f"MCP 服务 {mcp_id} 不存在")
            mcp_crud.check_access(mcp, user)

    async def _resolve_and_validate_bindings(
            self,
            user: User,
            conv: Conversation,
            *,
            knowledge_base_ids: Optional[List[str]] = None,
            skill_ids: Optional[List[str]] = None,
            mcp_ids: Optional[List[str]] = None,
            model_config_id: Optional[str] = None,
            enable_thinking: Optional[bool] = None,
            chat_skill_ids: Optional[List[str]] = None,
    ) -> ResolvedConversationBindings:
        """解析并校验 KB / Skill / MCP / 模型 / 深度思考绑定。"""
        resolved_kb = (
            knowledge_base_ids
            if knowledge_base_ids is not None
            else kb_ids_from_conversation(conv)
        )
        resolved_skill_ids = (
            skill_ids if skill_ids is not None else skill_ids_from_conversation(conv)
        )
        resolved_mcp_ids = (
            mcp_ids if mcp_ids is not None else mcp_ids_from_conversation(conv)
        )
        stream_skill_ids = (
            chat_skill_ids if chat_skill_ids is not None else resolved_skill_ids
        )

        if stream_skill_ids and resolved_mcp_ids:
            raise ParameterException(
                message="Skill 与 MCP 不能同时启用（请求中 skill_ids 与 mcp_ids 均非空）"
            )

        if resolved_kb:
            await self._validate_kb_access(resolved_kb, user)

        if resolved_skill_ids:
            await self._validate_skill_access(resolved_skill_ids, user)

        if chat_skill_ids is not None:
            if chat_skill_ids:
                if len(chat_skill_ids) > 1:
                    raise ParameterException(message="聊天仅支持选择一个 Skill")
                skill = await SkillCrud().get_skill(chat_skill_ids[0], user)
                mode = (skill.interaction_mode or "chat").lower()
                if mode != "chat":
                    raise ParameterException(
                        message=f"技能「{skill.name}」需通过 Skill 向导执行，不能直接在聊天中发起"
                    )
                if not skill.skill_key:
                    raise ParameterException(
                        message=f"技能「{skill.name}」未关联磁盘 Skill，请先在管理页同步"
                    )
        else:
            chat_only: List[str] = []
            for skill_id in resolved_skill_ids:
                skill = await SkillCrud().get_skill(skill_id, user)
                mode = (skill.interaction_mode or "chat").lower()
                if mode != "chat":
                    continue
                if not skill.skill_key:
                    raise ParameterException(
                        message=f"技能「{skill.name}」未关联磁盘 Skill，请先在管理页同步"
                    )
                chat_only.append(skill_id)
            if len(chat_only) > 1:
                raise ParameterException(message="聊天仅支持选择一个 Skill")

        if resolved_mcp_ids:
            await self._validate_mcp_access(resolved_mcp_ids, user)

        if model_config_id is not None:
            model_config = await ModelConfigCrud().resolve_for_chat(
                user, model_config_id
            )
            resolved_model_id = model_config.id if model_config else None
        else:
            model_config = await ModelConfigCrud().resolve_for_chat(
                user, conv.model_config_id
            )
            resolved_model_id = conv.model_config_id

        if enable_thinking is not None:
            stored_thinking = resolve_effective_enable_thinking(
                model_config, enable_thinking
            )
        else:
            stored_thinking = bool(conv.enable_thinking)

        return ResolvedConversationBindings(
            knowledge_base_ids=resolved_kb,
            skill_ids=resolved_skill_ids,
            mcp_ids=resolved_mcp_ids,
            model_config=model_config,
            model_config_id=resolved_model_id,
            enable_thinking=stored_thinking,
            chat_skill_ids=chat_skill_ids or [],
        )

    async def sync_conversation_bindings(
            self,
            user: User,
            conversation_id: str,
            data: ConversationBindingsUpdate,
    ) -> Conversation:
        """同步会话绑定（知识库 / 模型 / Skill / MCP），不写消息。"""
        conv = await self.get_by_id(conversation_id, user.id)
        if not conv:
            raise NotFoundException(message="对话不存在")

        bindings = await self._resolve_and_validate_bindings(
            user,
            conv,
            knowledge_base_ids=data.knowledge_base_ids,
            skill_ids=data.skill_ids,
            mcp_ids=data.mcp_ids,
            model_config_id=data.model_config_id,
            enable_thinking=data.enable_thinking,
        )

        await self.update_meta(
            conv,
            knowledge_base_ids=bindings.knowledge_base_ids,
            skill_ids=bindings.skill_ids,
            mcp_ids=bindings.mcp_ids,
            model_config_id=bindings.model_config_id,
            enable_thinking=bindings.enable_thinking,
        )
        await self._sync_active_skill_run_bindings(
            user,
            conv.id,
            model_config_id=bindings.model_config_id,
            knowledge_base_ids=bindings.knowledge_base_ids,
        )
        return conv

    async def _sync_active_skill_run_bindings(
            self,
            user: User,
            conversation_id: str,
            *,
            model_config_id: Optional[str] = None,
            knowledge_base_ids: Optional[List[str]] = None,
    ) -> None:
        """收集阶段同步草稿 Run 的模型 / 知识库，与对话绑定保持一致。"""
        run_crud = SkillRunCrud()
        run = await run_crud.get_active_draft(user, conversation_id)
        if not run:
            return
        changed = False
        if model_config_id is not None and run.model_config_id != model_config_id:
            run.model_config_id = model_config_id
            changed = True
        if knowledge_base_ids is not None and (run.knowledge_base_ids or []) != knowledge_base_ids:
            run.knowledge_base_ids = knowledge_base_ids
            changed = True
        if changed:
            await run.save()

    async def prepare_for_chat(
            self, req: ChatRequest, user: User
    ) -> tuple[Conversation, Optional[ModelConfig], List[Dict[str, Any]], list[str], list[str], list[str]]:
        """准备聊天上下文"""
        if req.conversation_id:
            conv = await self.get_by_id(req.conversation_id, user.id)
            if not conv:
                raise NotFoundException(message="对话不存在")
        else:
            conv = await self.create_for_user(user.id)

        conv_skill_ids = skill_ids_from_conversation(conv)
        _, conv_wizard_ids = (
            await self._partition_skill_ids(conv_skill_ids, user)
            if conv_skill_ids else ([], [])
        )
        if req.skill_ids is not None:
            chat_skill_ids = req.skill_ids
        else:
            chat_skill_ids, _ = (
                await self._partition_skill_ids(conv_skill_ids, user)
                if conv_skill_ids else ([], [])
            )
        stored_skill_ids = list(dict.fromkeys(conv_wizard_ids + chat_skill_ids))

        bindings = await self._resolve_and_validate_bindings(
            user,
            conv,
            knowledge_base_ids=req.knowledge_base_ids,
            skill_ids=stored_skill_ids,
            mcp_ids=req.mcp_ids,
            model_config_id=req.model_config_id,
            enable_thinking=req.enable_thinking,
            chat_skill_ids=chat_skill_ids,
        )

        await self.update_meta(
            conv,
            knowledge_base_ids=bindings.knowledge_base_ids,
            skill_ids=bindings.skill_ids,
            mcp_ids=bindings.mcp_ids,
            model_config_id=bindings.model_config_id,
            enable_thinking=bindings.enable_thinking,
        )

        history_msgs = await self.message.list_by_conversation(conv.id)
        chat_history = [{"role": m.role.value, "content": m.content} for m in history_msgs]

        if not history_msgs:
            title = req.question[:20] + ("..." if len(req.question) > 20 else "")
            await self.update_meta(conv, title=title)

        await self.message.add_message(conv.id, ChatMessageRole.USER, req.question)

        return (
            conv,
            bindings.model_config,
            chat_history,
            bindings.knowledge_base_ids,
            bindings.mcp_ids,
            bindings.chat_skill_ids,
        )

    async def stream_response(
            self,
            question: str,
            knowledge_base_ids: List[str],
            chat_history: List[dict],
            model_config: Optional[ModelConfig],
            mcp_ids: Optional[List[str]] = None,
            skill_ids: Optional[List[str]] = None,
            user: Optional[User] = None,
            conversation_id: Optional[str] = None,
            enable_thinking: bool = False,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式生成聊天回复"""
        llm_params = resolve_chat_llm_params(model_config)
        effective_thinking = resolve_effective_enable_thinking(
            model_config, enable_thinking
        )

        if skill_ids and user and conversation_id:
            async for chunk in skill_agent_stream(
                    question=question,
                    knowledge_base_ids=knowledge_base_ids,
                    chat_history=chat_history,
                    skill_ids=skill_ids,
                    user=user,
                    conversation_id=conversation_id,
                    enable_thinking=effective_thinking,
                    **llm_params,
            ):
                yield chunk
            return

        if mcp_ids and user:
            async for chunk in _mcp_orchestrator.stream(
                    question=question,
                    mcp_server_ids=mcp_ids,
                    user=user,
                    knowledge_base_ids=knowledge_base_ids,
                    chat_history=chat_history,
                    enable_thinking=effective_thinking,
                    mcp_system_prompt=MCP_AGENT_SYSTEM_PROMPT,
                    conversation_id=conversation_id,
                    **llm_params,
            ):
                yield chunk
            return

        async for chunk in rag_stream(
                question=question,
                knowledge_base_ids=knowledge_base_ids,
                chat_history=chat_history,
                enable_thinking=effective_thinking,
                **llm_params,
        ):
            yield chunk

    @staticmethod
    def _build_skill_intake_payload(skill, run, *, phase: str = "collecting", step_index: int = 0) -> dict:
        return {
            "run_id": run.id,
            "skill_id": skill.id,
            "skill_name": skill.name,
            "skill_key": skill.skill_key,
            "interaction_mode": (skill.interaction_mode or "wizard").lower(),
            "phase": phase,
            "step_index": step_index,
            "form_values": dict(run.input_data or {}),
            "file_labels": {},
            "missing_fields": [],
            "run_summary": "",
            "process_trace": [],
        }

    async def start_skill_intake(
            self,
            user: User,
            conversation_id: str,
            skill_id: str,
            *,
            model_config_id: Optional[str] = None,
            knowledge_base_ids: Optional[List[str]] = None,
            enable_thinking: bool = False,
            force_new: bool = False,
    ) -> SkillIntakeStartResult:
        conv = await self.get_by_id(conversation_id, user.id)
        if not conv:
            raise NotFoundException(message="对话不存在")

        run_crud = SkillRunCrud()
        skill_crud = SkillCrud()
        skill = await skill_crud.get_skill(skill_id, user)
        mode = (skill.interaction_mode or "chat").lower()
        if mode not in SkillRunCrud.RUN_MODES:
            raise ParameterException(message=f"技能「{skill.name}」不支持对话内收集")

        model_config = await ModelConfigCrud().resolve_for_chat(
            user, model_config_id
        )
        if knowledge_base_ids is not None:
            kb_ids = knowledge_base_ids
        else:
            kb_ids = kb_ids_from_conversation(conv)
        if kb_ids:
            await self._validate_kb_access(kb_ids, user)

        resolved_model_id = model_config.id if model_config else None
        stored_thinking = resolve_effective_enable_thinking(
            model_config, enable_thinking
        )

        active = await run_crud.get_active_draft(user, conversation_id)
        if active and not force_new:
            if active.skill_id == skill_id:
                message = await self.message.find_intake_message(conversation_id, active.id)
                if message:
                    intake = message.skill_intake or self._build_skill_intake_payload(skill, active)
                    await self.update_meta(
                        conv,
                        knowledge_base_ids=kb_ids,
                        skill_ids=[skill_id],
                        mcp_ids=[],
                        model_config_id=resolved_model_id,
                        enable_thinking=stored_thinking,
                    )
                    return SkillIntakeStartResult(
                        conversation_id=conversation_id,
                        message_id=message.id,
                        run_id=active.id,
                        skill_intake=intake,
                        resumed=True,
                        title=conv.title,
                    )
            raise ParameterException(
                message="当前对话已有进行中的 Skill 收集，请先取消或完成后再选择其他 Skill"
            )

        if active and force_new:
            await run_crud.cancel_run(active.id, user)

        run = await run_crud.create_run(
            user,
            SkillRunCreate(
                skill_id=skill_id,
                conversation_id=conversation_id,
                model_config_id=resolved_model_id,
                knowledge_base_ids=kb_ids or None,
            ),
        )
        intake = self._build_skill_intake_payload(skill, run)
        message = await self.message.add_message(
            conversation_id,
            ChatMessageRole.ASSISTANT,
            " ",
            skill_intake=intake,
        )
        title = f"Skill 收集 · {skill.name}"
        await self.update_meta(
            conv,
            knowledge_base_ids=kb_ids,
            skill_ids=[skill_id],
            mcp_ids=[],
            model_config_id=resolved_model_id,
            enable_thinking=stored_thinking,
            title=title,
        )
        return SkillIntakeStartResult(
            conversation_id=conversation_id,
            message_id=message.id,
            run_id=run.id,
            skill_intake=intake,
            resumed=False,
            title=title,
        )

    async def begin_skill_run_reply(
            self,
            user: User,
            run_id: str,
            *,
            is_async: bool = False,
    ) -> Optional[int]:
        """冻结向导消息并创建独立的模型执行回复消息。"""
        from backend.applications.agent.models.agent_model import SkillRun
        from backend.applications.agent.services.skill_run_executor import (
            build_skill_run_ref,
        )

        run = await SkillRun.get_or_none(id=run_id, user_id=user.id, state__not=1)
        if not run or not run.conversation_id:
            return None

        conv = await self.get_by_id(run.conversation_id, user.id)
        if conv:
            kb_ids = list(run.knowledge_base_ids or [])
            await self.update_meta(
                conv,
                knowledge_base_ids=kb_ids,
                skill_ids=[run.skill_id],
                mcp_ids=[],
                model_config_id=run.model_config_id,
            )

        skill = await SkillCrud().get_skill(run.skill_id, user)
        intake_msg = await self.message.find_intake_message(run.conversation_id, run_id)
        if intake_msg:
            frozen = freeze_intake_as_submitted(
                intake_msg.skill_intake,
                skill.input_schema,
            )
            if frozen != intake_msg.skill_intake:
                intake_msg.skill_intake = frozen
                await intake_msg.save()

        existing = await self.message.find_execution_message(run.conversation_id, run_id)
        if existing:
            return existing.id

        skill_run_ref = build_skill_run_ref(run, skill)
        intro = (
            "异步任务已提交，正在后台执行…"
            if is_async
            else "任务执行中…"
        )
        exec_msg = await self.message.add_message(
            run.conversation_id,
            ChatMessageRole.ASSISTANT,
            intro,
            skill_run_ref=skill_run_ref,
        )
        return exec_msg.id

    async def list_conversation_stats_by_user(
            self,
            user_id: int,
            page: int = 1,
            page_size: int = 10,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
    ) -> tuple[int, List[ConversationStatOut]]:
        """按用户 ID 分页查询各对话的统计详情（轮次、Token 消耗等）"""
        user = await User.get_or_none(id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        qs = self.model.filter(user_id=user_id, state__not=1)
        if start_time and end_time:
            qs = qs.filter(updated_time__range=[start_time, end_time])
        elif start_time:
            qs = qs.filter(updated_time__gte=start_time)
        elif end_time:
            qs = qs.filter(updated_time__lte=end_time)

        total = await qs.count()
        conversations = (
            await qs.prefetch_related(
                "model_config",
                Prefetch("messages", Message.filter(state__not=1)),
            )
            .order_by("-updated_time")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        all_kb_ids: set[str] = set()
        for conv in conversations:
            all_kb_ids.update(kb_ids_from_conversation(conv))

        kb_map: dict[str, KnowledgeBase] = {}
        if all_kb_ids:
            kbs = await KnowledgeBase.filter(id__in=list(all_kb_ids))
            kb_map = {kb.id: kb for kb in kbs}

        user_brief = UserBrief(id=user.id, username=user.username, alias=user.alias)
        results: List[ConversationStatOut] = []

        for conv in conversations:
            assistant_msgs = [
                m for m in conv.messages if m.role == ChatMessageRole.ASSISTANT
            ]
            prompt_sum = sum(m.prompt_tokens or 0 for m in assistant_msgs)
            completion_sum = sum(m.completion_tokens or 0 for m in assistant_msgs)
            reasoning_sum = sum(m.reasoning_tokens or 0 for m in assistant_msgs)

            kb_briefs: List[KnowledgeBaseBrief] = []
            for kb_id in kb_ids_from_conversation(conv):
                kb = kb_map.get(kb_id)
                if kb:
                    kb_briefs.append(
                        KnowledgeBaseBrief(
                            id=kb.id,
                            name=kb.knowledge_name,
                            description=kb.description,
                        )
                    )
                else:
                    kb_briefs.append(KnowledgeBaseBrief(id=kb_id))

            model_brief = None
            if conv.model_config:
                model_brief = ModelConfigBrief(
                    id=conv.model_config.id,
                    config_name=conv.model_config.config_name,
                    config_desc=conv.model_config.config_desc,
                )

            results.append(
                ConversationStatOut(
                    conversation=ConversationBrief(id=conv.id, title=conv.title),
                    model_config_info=model_brief,
                    knowledge_bases=kb_briefs,
                    round_count=len(assistant_msgs),
                    token_usage=TokenUsage(
                        prompt_tokens=prompt_sum,
                        completion_tokens=completion_sum,
                        reasoning_tokens=reasoning_sum,
                        total_tokens=prompt_sum + completion_sum + reasoning_sum,
                    ),
                    user=user_brief,
                )
            )

        return total, results
