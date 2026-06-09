from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    TimestampMixin,
    unique_identify
)


class KnowledgeBase(ScaffoldModel, TimestampMixin):
    """知识库"""

    id = fields.CharField(default=unique_identify, max_length=64, pk=True)
    name = fields.CharField(max_length=128)
    description = fields.TextField(null=True)
    owner = fields.ForeignKeyField(
        "models.User",
        related_name="knowledge_bases",
        on_delete=fields.CASCADE
    )
    is_public = fields.BooleanField(default=False)

    documents: fields.ReverseRelation["Document"]

    class Meta:
        table = "keenrobot_knowledge_bases"


class Document(ScaffoldModel, TimestampMixin):
    """文档"""

    id = fields.CharField(default=unique_identify, max_length=64, pk=True)
    kb = fields.ForeignKeyField(
        "models.KnowledgeBase",
        related_name="documents",
        on_delete=fields.CASCADE
    )
    filename = fields.CharField(max_length=255)
    file_path = fields.CharField(max_length=512)
    file_size = fields.IntField()
    chunk_count = fields.IntField(default=0)
    status = fields.CharField(max_length=32, default="processing")
    error_msg = fields.TextField(null=True)

    chunks: fields.ReverseRelation["DocumentChunk"]

    class Meta:
        table = "keenrobot_documents"


class DocumentChunk(ScaffoldModel, TimestampMixin):
    """文档分块"""

    id = fields.CharField(default=unique_identify, max_length=64, pk=True)
    doc = fields.ForeignKeyField(
        "models.Document",
        related_name="chunks",
        on_delete=fields.CASCADE
    )
    content = fields.TextField()
    chunk_index = fields.IntField()
    chroma_id = fields.CharField(max_length=128, null=True)

    class Meta:
        table = "keenrobot_document_chunks"
