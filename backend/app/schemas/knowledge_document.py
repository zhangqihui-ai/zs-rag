from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


KnowledgeDocumentStatus = str
KnowledgeChunkVectorStatus = str


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class KnowledgeDocumentResponse(BaseModel):
    id: int
    enterprise_space_id: int
    knowledge_base_id: int
    source_type: str
    document_name: str
    file_name: str
    file_ext: str | None
    mime_type: str | None
    file_size: int | None
    storage_type: str
    parser_type: str
    chunk_size: int
    chunk_overlap: int
    status: str
    chunk_count: int
    token_count: int | None
    char_count: int | None
    error_message: str | None
    metadata: dict | None = None
    chunking_config: dict | None = None
    upload_skipped: bool = False
    skip_reason: str | None = None
    last_parsed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentChunkingConfigUpdate(BaseModel):
    """文档级分段策略覆盖：为空代表继承知识库默认。"""

    chunking_config: dict | None = Field(default=None)


class KnowledgeDocumentChunkingPreviewRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    chunking_config: dict = Field(default_factory=dict, description="分段配置（chunking_config_json 结构）")
    max_pages: int = Field(
        default=2,
        ge=1,
        le=5,
        description="兼容字段：预览原文与切片已按全文真实分块对齐，不再按页拼接；可忽略。",
    )
    max_chars: int = Field(
        default=8000,
        ge=500,
        le=50000,
        description="左侧原文展示长度上限（按本批预览切片在全文中的 offset 区间截取后再截断）",
    )
    max_chunks: int = Field(default=40, ge=1, le=200, description="返回分块上限")


class ParentChildPreviewChildItem(BaseModel):
    chunk_index: int
    content: str
    char_count: int


class ParentChildPreviewGroupItem(BaseModel):
    parent_index: int
    parent_preview: str
    parent_char_count: int = Field(default=0, description="父块全文字符数")
    children: list[ParentChildPreviewChildItem]


class KnowledgeDocumentChunkingPreviewResponse(BaseModel):
    document_id: int
    file_name: str
    mode: str
    excerpt: str
    chunks: list[str]
    total_chunks: int = Field(..., description="与正式索引相同的全量分块数")
    preview_chunk_count: int = Field(..., description="本响应中返回的块数（不超过 max_chunks）")
    excerpt_truncated: bool = Field(default=False, description="是否因 max_chars 截断了左侧原文")
    parent_child_groups: list[ParentChildPreviewGroupItem] | None = Field(
        default=None,
        description="父子模式：按父块分组的子段（child_delimiter 切段，用于预览 C-1/C-2；与向量块数量可不一致）",
    )


class DocumentFileExtOption(BaseModel):
    value: str
    label: str
    count: int


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentResponse]
    total: int
    page: int
    page_size: int
    file_ext_options: list[DocumentFileExtOption] = Field(default_factory=list)


class KnowledgeChunkResponse(BaseModel):
    id: int
    chunk_uid: str
    document_id: int
    chunk_index: int
    content: str
    content_preview: str | None
    char_count: int
    token_count: int | None
    start_offset: int | None
    end_offset: int | None
    page_no: int | None
    heading_path: str | None
    vector_status: str
    vector_id: str | None
    keyword_text: str | None = None
    enrichment_keywords: list[str] = Field(default_factory=list)
    enrichment_questions: list[str] = Field(default_factory=list)
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeChunkEnrichmentUpdate(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=12)
    questions: list[str] = Field(default_factory=list, max_length=5)


class KnowledgeChunkEnrichmentRegenerateResponse(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ChunkSourceContextResponse(BaseModel):
    text: str
    highlight_start: int = 0
    highlight_end: int = 0
    start_offset: int | None = None
    end_offset: int | None = None
    truncated_before: bool = False
    truncated_after: bool = False
    fallback: bool = False


class KnowledgeChunkListResponse(BaseModel):
    items: list[KnowledgeChunkResponse]
    total: int
    page: int
    page_size: int


class DocumentUploadOptions(BaseModel):
    chunk_size: int | None = Field(default=None, ge=100, le=5000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)
    embedding_model_id: int | None = Field(default=None)


class ParseLogLineItem(BaseModel):
    t: str = ""
    text: str = ""


class KnowledgeDocumentParseLogResponse(BaseModel):
    kind: str | None = None
    phase: str | None = None
    lines: list[ParseLogLineItem] = Field(default_factory=list)
    updated_at: str | None = None
