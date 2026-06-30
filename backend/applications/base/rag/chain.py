# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : chain.py
@DateTime: 2025/4/28 18:07
"""
"""RAG检索增强生成链"""

import re
import asyncio
from collections.abc import AsyncIterator
from typing import List, Dict, Any

from backend.configure.rag_config import (
    CHAT_GREETING_CANNED_REPLY,
    resolve_chat_system_prompt,
)
from backend.applications.base.rag.llm import OpenAICompatibleLLM, format_messages
from backend.applications.base.rag.retriever import retrieve


def is_irrelevant_question(question: str) -> bool:
    """检查问题是否与知识库无关"""
    # 无关问题关键词列表
    irrelevant_patterns = [
        r'^你好$', r'^您好$', r'^hi$', r'^hello$',
        r'^你是谁$', r'^你叫什么$', r'^你是什么模型$',
        r'^你能做什么$', r'^介绍一下自己$', r'^介绍.*自己',
        r'^你会什么$', r'^你有.*功能',
    ]

    question_stripped = question.strip()
    for pattern in irrelevant_patterns:
        if re.match(pattern, question_stripped, re.IGNORECASE):
            return True
    return False


async def stream_irrelevant_response() -> AsyncIterator[Dict[str, Any]]:
    """无关问题标准回复（模拟流式输出）。"""
    await asyncio.sleep(1.5)
    for char in CHAT_GREETING_CANNED_REPLY:
        yield {"type": "content", "content": char}
        if char in ["，", "。", "！", "？", "：", "\n"]:
            await asyncio.sleep(0.05)
        else:
            await asyncio.sleep(0.02)


def _resolve_system_prompt(
        system_prompt: str = None,
        context: str = "",
        has_context: bool = True,
        retrieval_attempted: bool = False,
) -> str:
    """兼容旧调用方；新代码请使用 rag_config.resolve_chat_system_prompt。"""
    return resolve_chat_system_prompt(
        custom_system_prompt=system_prompt,
        kb_context=context,
        has_kb_context=has_context,
        kb_retrieval_was_empty=retrieval_attempted,
    )


def rag_query(
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]] = None,
        model_name: str = "qwen-turbo",
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        system_prompt: str = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        max_history_rounds: int = 10,
) -> str:
    """
    同步RAG问答

    Args:
        question: 用户问题
        knowledge_base_ids: 知识库ID列表
        chat_history: 历史对话
        model_name: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        top_p: top-p采样
        system_prompt: 自定义系统提示词
        top_k: 检索返回条数
        score_threshold: 检索相似度阈值
        max_history_rounds: 保留历史对话轮数

    Returns:
        模型回答
    """
    # 1. 向量检索
    outcome = retrieve(
        question,
        knowledge_base_ids,
        chat_history=chat_history,
        top_k=top_k,
        score_threshold=score_threshold,
    )
    has_context = bool(outcome.items) and len(outcome.context.strip()) > 0
    resolved_prompt = _resolve_system_prompt(
        system_prompt=system_prompt,
        context=outcome.context if has_context else "",
        has_context=has_context,
        retrieval_attempted=outcome.retrieval_attempted and outcome.is_empty,
    )

    # 2. 构建消息
    messages = format_messages(
        system_prompt=resolved_prompt,
        user_question=question,
        context=outcome.context,
        chat_history=chat_history,
        max_history_rounds=max_history_rounds,
        format_context=False,
    )

    # 3. 调用LLM
    llm = OpenAICompatibleLLM(model=model_name, api_key=api_key, base_url=base_url)
    response = llm.chat(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )

    return response


async def rag_stream(
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[Dict[str, str]] = None,
        model_name: str = "qwen-turbo",
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        system_prompt: str = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        max_history_rounds: int = 10,
        enable_thinking: bool = False,
        user=None,
        conversation_id: str = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    流式 RAG 问答（薄封装 → ChatAgentOrchestrator，无 Skill/MCP）。

    保留此函数以兼容旧调用方；新代码请直接使用 ChatAgentOrchestrator.stream。
    """
    if user is None:
        raise ValueError("rag_stream 需要 user 参数，请改用 ChatAgentOrchestrator.stream")

    from backend.applications.agent.orchestrator.chat_agent_orchestrator import ChatAgentOrchestrator

    orchestrator = ChatAgentOrchestrator()
    async for chunk in orchestrator.stream(
            question=question,
            user=user,
            conversation_id=conversation_id,
            skill_ids=[],
            mcp_server_ids=[],
            knowledge_base_ids=knowledge_base_ids,
            chat_history=chat_history,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            system_prompt=system_prompt,
            top_k=top_k,
            score_threshold=score_threshold,
            max_history_rounds=max_history_rounds,
            enable_thinking=enable_thinking,
    ):
        yield chunk
