# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/4/28 18:07
"""
from backend.applications.base.rag.chain import (
    is_irrelevant_question,
    get_irrelevant_response,
    format_context_from_results,
    rag_query,
    rag_stream,
)
from backend.applications.base.rag.chroma_store import chroma_store
from backend.applications.base.rag.embeddings import (
    is_embedding_configured,
    get_embedding,
    get_single_embedding,
)
from backend.applications.base.rag.llm import (
    OpenAICompatibleLLM,
    format_messages,
)
from backend.applications.base.rag.loader import (
    load_pdf,
    load_all_pdfs,
    split_documents,
)

__all__ = [
    "load_pdf", "load_all_pdfs", "split_documents",
    "is_irrelevant_question", "get_irrelevant_response", "format_context_from_results", "rag_query", "rag_stream",
    "chroma_store",
    "is_embedding_configured", "get_embedding", "get_single_embedding",
    "OpenAICompatibleLLM", "format_messages",
]
