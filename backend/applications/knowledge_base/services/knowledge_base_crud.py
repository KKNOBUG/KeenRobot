# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : knowledge_base_crud.py
@DateTime: 2026/6/9
"""
import hashlib
import os
import uuid
from typing import List, Optional, Tuple

from fastapi import UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from tortoise.expressions import Q

from backend.applications.base.rag.chroma_store import chroma_store
from backend.applications.base.rag.embeddings import get_embedding
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.knowledge_base.services.document_loader import load_document_pages
from backend.applications.knowledge_base.services.file_type import validate_file_type
from backend.applications.knowledge_base.models.knowledge_base_model import (
    Document,
    DocumentChunk,
    KnowledgeBase,
)
from backend.applications.knowledge_base.schemas.knowledge_base_schema import (
    DocumentChunkOut,
    DocumentChunkUpdate,
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
)
from backend.applications.user.models.user_model import User
from backend.configure import PROJECT_CONFIG
from backend.core.exceptions import (
    DataBaseStorageException,
    NoPermissionException,
    NotFoundException,
    ParameterException,
)


class _DocumentCreate(BaseModel):
    kb_id: str
    filename: str
    file_type: str
    file_path: str
    file_size: int
    content_hash: str
    embedding_model: Optional[str] = None
    status: str = "processing"


class _DocumentUpdate(BaseModel):
    status: Optional[str] = None
    chunk_count: Optional[int] = None
    error_msg: Optional[str] = None


class _DocumentChunkCreate(BaseModel):
    doc_id: str
    content: str
    chunk_index: int
    page_number: Optional[int] = None


class DocumentCrud(ScaffoldCrud[Document, _DocumentCreate, _DocumentUpdate]):
    def __init__(self):
        super().__init__(model=Document)

    async def get_by_kb(self, kb_id: str, doc_id: str) -> Optional[Document]:
        """根据知识库 ID 和文档 ID 获取文档"""
        return await self.model.get_or_none(id=doc_id, kb_id=kb_id)

    async def get_by_content_hash(self, kb_id: str, content_hash: str) -> Optional[Document]:
        """根据知识库 ID 和内容哈希获取文档"""
        return await self.model.get_or_none(kb_id=kb_id, content_hash=content_hash)

    async def list_by_kb(self, kb_id: str) -> List[Document]:
        """获取知识库下的文档列表"""
        return await self.model.filter(kb_id=kb_id).order_by("-created_time")

    async def count_by_kb(self, kb_id: str) -> int:
        """统计知识库下的文档数量"""
        return await self.model.filter(kb_id=kb_id).count()

    async def create_for_kb(self, kb_id: str, **kwargs) -> Document:
        """在指定知识库下创建文档"""
        return await self.model.create(kb_id=kb_id, **kwargs)


class DocumentChunkCrud(ScaffoldCrud[DocumentChunk, _DocumentChunkCreate, DocumentChunkUpdate]):
    def __init__(self):
        super().__init__(model=DocumentChunk)

    async def bulk_create_chunks(self, chunks: List[DocumentChunk]) -> None:
        """批量创建文档分块"""
        await self.model.bulk_create(chunks)

    async def list_by_kb(
        self,
        kb_id: str,
        doc_id: str = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[DocumentChunk]:
        """获取知识库下的文档分块列表"""
        qs = self.model.filter(doc__kb_id=kb_id)
        if doc_id:
            qs = qs.filter(doc_id=doc_id)
        offset = (page - 1) * page_size
        return await qs.order_by("chunk_index").offset(offset).limit(page_size)

    async def get_by_kb(self, kb_id: str, chunk_id: str) -> Optional[DocumentChunk]:
        """根据知识库 ID 和分块 ID 获取文档分块"""
        return (
            await self.model.filter(id=chunk_id, doc__kb_id=kb_id)
            .prefetch_related("doc")
            .first()
        )

    async def count_by_doc(self, doc_id: str) -> int:
        """统计文档下的分块数量"""
        return await self.model.filter(doc_id=doc_id).count()


class KnowledgeBaseCrud(ScaffoldCrud[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseCreate]):
    def __init__(self):
        super().__init__(model=KnowledgeBase)
        self.document = DocumentCrud()
        self.chunk = DocumentChunkCrud()

    @staticmethod
    def _operator_name(user: User) -> str:
        """截取用户名以适配 MaintainMixin 字段长度"""
        return (user.username or "")[:16]

    @staticmethod
    def _content_hash(content: bytes) -> str:
        """计算文件内容 SHA256"""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _resolve_chunk_config(kb: KnowledgeBase) -> Tuple[int, int]:
        """解析知识库分块参数，未配置时回退全局默认值"""
        chunk_size = kb.chunk_size or PROJECT_CONFIG.CHUNK_SIZE
        chunk_overlap = kb.chunk_overlap if kb.chunk_overlap is not None else PROJECT_CONFIG.CHUNK_OVERLAP
        if chunk_overlap > chunk_size // 2:
            chunk_overlap = chunk_size // 2
        return chunk_size, chunk_overlap

    async def get_by_id(self, kb_id: str) -> Optional[KnowledgeBase]:
        """根据 ID 获取知识库（排除已禁用）"""
        return await self.model.filter(id=kb_id, state__not=1).first()

    async def list_for_user(
        self, user_id: int, search: str = None
    ) -> List[KnowledgeBase]:
        """获取用户可见的知识库列表"""
        qs = self.model.filter(
            Q(owner_id=user_id) | Q(is_public=True),
            state__not=1,
        )
        if search:
            qs = qs.filter(
                Q(knowledge_name__icontains=search) | Q(description__icontains=search)
            )
        return await qs.order_by("-updated_time")

    def check_access(self, kb: KnowledgeBase, user: User) -> None:
        """校验知识库访问权限"""
        if not kb.is_public and kb.owner_id != user.id and not user.is_superuser:
            raise NoPermissionException(message="没有权限访问该知识库")

    def check_write(self, kb: KnowledgeBase, user: User) -> None:
        """校验知识库写权限"""
        if kb.owner_id != user.id and not user.is_superuser:
            raise NoPermissionException(message="没有权限操作该知识库")

    @staticmethod
    def _to_document_out(doc: Document) -> DocumentOut:
        return DocumentOut(
            id=doc.id,
            kb_id=doc.kb_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            content_hash=doc.content_hash,
            embedding_model=doc.embedding_model,
            chunk_count=doc.chunk_count,
            status=doc.status,
            error_msg=doc.error_msg,
            created_time=doc.created_time,
            updated_time=doc.updated_time,
        )

    @staticmethod
    def _to_chunk_out(chunk: DocumentChunk) -> DocumentChunkOut:
        return DocumentChunkOut(
            id=chunk.id,
            doc_id=chunk.doc_id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            created_time=chunk.created_time,
            updated_time=chunk.updated_time,
        )

    async def _to_out(self, kb: KnowledgeBase) -> KnowledgeBaseOut:
        doc_count = await self.document.count_by_kb(kb.id)
        return KnowledgeBaseOut(
            id=kb.id,
            knowledge_name=kb.knowledge_name,
            description=kb.description,
            owner_id=kb.owner_id,
            is_public=kb.is_public,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            created_time=kb.created_time,
            updated_time=kb.updated_time,
            document_count=doc_count,
        )

    async def create_kb(self, user: User, data: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        """创建知识库"""
        operator = self._operator_name(user)
        kb = await self.model.create(
            owner_id=user.id,
            knowledge_name=data.knowledge_name,
            description=data.description,
            is_public=data.is_public,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            created_user=operator,
            updated_user=operator,
        )
        return await self._to_out(kb)

    async def list_kbs(self, user: User, search: str = None) -> List[KnowledgeBaseOut]:
        """获取当前用户可见的知识库列表"""
        kbs = await self.list_for_user(user.id, search)
        return [await self._to_out(kb) for kb in kbs]

    async def get_kb(self, kb_id: str, user: User) -> KnowledgeBaseOut:
        """获取知识库详情"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        return await self._to_out(kb)

    async def update_kb(
        self, kb_id: str, user: User, data: KnowledgeBaseCreate
    ) -> KnowledgeBaseOut:
        """更新知识库"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        kb.knowledge_name = data.knowledge_name
        kb.description = data.description
        kb.is_public = data.is_public
        kb.chunk_size = data.chunk_size
        kb.chunk_overlap = data.chunk_overlap
        kb.updated_user = self._operator_name(user)
        await kb.save()
        return await self._to_out(kb)

    async def delete_kb(self, kb_id: str, user: User) -> None:
        """软删除知识库（state=1），并清理向量索引"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chroma_store.delete_by_kb(kb_id)
        kb.state = 1
        kb.updated_user = self._operator_name(user)
        await kb.save()

    async def upload_document(
        self, kb_id: str, user: User, file: UploadFile
    ) -> DocumentOut:
        """上传并处理文档"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)

        try:
            file_type = validate_file_type(file.filename)
        except ValueError as e:
            raise ParameterException(message=str(e))

        content = await file.read()
        content_hash = self._content_hash(content)

        existing_doc = await self.document.get_by_content_hash(kb_id, content_hash)
        if existing_doc:
            raise ParameterException(
                message=(
                    f"该文档内容已存在于当前知识库"
                    f"（与「{existing_doc.filename}」相同），请勿重复上传"
                )
            )

        kb_upload_dir = PROJECT_CONFIG.upload_path / kb_id
        kb_upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = kb_upload_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        embedding_model = PROJECT_CONFIG.DEFAULT_EMBEDDING_MODEL
        doc = await self.document.create_for_kb(
            kb_id=kb_id,
            filename=file.filename,
            file_type=file_type,
            file_path=str(file_path),
            file_size=len(content),
            content_hash=content_hash,
            embedding_model=embedding_model,
            status="processing",
        )

        try:
            chunk_size, chunk_overlap = self._resolve_chunk_config(kb)
            pages = load_document_pages(str(file_path), file_type)
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", "。", "；", "，", " ", ""],
            )

            chunk_models: List[DocumentChunk] = []
            chunk_index = 0
            for page in pages:
                raw_page = page.metadata.get("page")
                page_number = int(raw_page) + 1 if raw_page is not None else None
                for chunk_text in splitter.split_text(page.page_content):
                    chunk_models.append(
                        DocumentChunk(
                            id=str(uuid.uuid4()),
                            doc_id=doc.id,
                            content=chunk_text,
                            chunk_index=chunk_index,
                            page_number=page_number,
                        )
                    )
                    chunk_index += 1

            await self.chunk.bulk_create_chunks(chunk_models)

            embeddings = get_embedding([c.content for c in chunk_models])
            chroma_chunks = [
                {
                    "doc_id": doc.id,
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "embedding": emb,
                    "page_number": chunk.page_number,
                    "filename": doc.filename,
                    "embedding_model": embedding_model,
                }
                for chunk, emb in zip(chunk_models, embeddings)
            ]
            chroma_ids = chroma_store.upsert_chunks(kb_id, chroma_chunks)

            for chunk, chroma_id in zip(chunk_models, chroma_ids):
                chunk.chroma_id = chroma_id
                await chunk.save()

            doc.status = "completed"
            doc.chunk_count = len(chunk_models)
            await doc.save()
        except Exception as e:
            doc.status = "failed"
            doc.error_msg = str(e)
            await doc.save()
            raise DataBaseStorageException(message=f"文档处理失败: {str(e)}")

        return self._to_document_out(doc)

    async def list_documents(self, kb_id: str, user: User) -> List[DocumentOut]:
        """获取知识库下的文档列表"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        docs = await self.document.list_by_kb(kb_id)
        return [self._to_document_out(doc) for doc in docs]

    async def delete_document(self, kb_id: str, doc_id: str, user: User) -> None:
        """删除文档"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        doc = await self.document.get_by_kb(kb_id, doc_id)
        if not doc:
            raise NotFoundException(message="文档不存在")
        chroma_store.delete_by_doc(doc_id)
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        await doc.delete()

    async def list_chunks(
        self,
        kb_id: str,
        user: User,
        doc_id: str = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[DocumentChunkOut]:
        """获取知识库下的文档分块列表"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        chunks = await self.chunk.list_by_kb(kb_id, doc_id, page, page_size)
        return [self._to_chunk_out(chunk) for chunk in chunks]

    async def get_chunk(self, kb_id: str, chunk_id: str, user: User) -> DocumentChunkOut:
        """获取文档分块详情"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")
        return self._to_chunk_out(chunk)

    async def update_chunk(
        self, kb_id: str, chunk_id: str, user: User, data: DocumentChunkUpdate
    ) -> DocumentChunkOut:
        """更新文档分块"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")

        chunk.content = data.content
        embedding = get_embedding([data.content])[0]
        if chunk.chroma_id:
            chroma_store.delete_by_vector_id(chunk.chroma_id)
        filename = chunk.doc.filename if chunk.doc else None
        embedding_model = chunk.doc.embedding_model if chunk.doc else None
        chroma_ids = chroma_store.upsert_chunks(
            kb_id,
            [
                {
                    "doc_id": chunk.doc_id,
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "embedding": embedding,
                    "page_number": chunk.page_number,
                    "filename": filename,
                    "embedding_model": embedding_model,
                }
            ],
        )
        chunk.chroma_id = chroma_ids[0]
        await chunk.save()
        return self._to_chunk_out(chunk)

    async def delete_chunk(self, kb_id: str, chunk_id: str, user: User) -> None:
        """删除文档分块"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")
        if chunk.chroma_id:
            chroma_store.delete_by_vector_id(chunk.chroma_id)
        doc_id = chunk.doc_id
        await chunk.delete()
        doc = await self.document.get_by_kb(kb_id, doc_id)
        if doc:
            doc.chunk_count = await self.chunk.count_by_doc(doc_id)
            await doc.save()
