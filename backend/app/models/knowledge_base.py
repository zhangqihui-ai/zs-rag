from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeBaseStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EMBEDDING_UNAVAILABLE = "embedding_unavailable"
    DELETED = "deleted"


class KnowledgeDocumentStatus(enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INDEXED = "indexed"
    GRAPH_INDEXING = "graph_indexing"
    GRAPH_INDEXED = "graph_indexed"
    GRAPH_FAILED = "graph_failed"
    FAILED = "failed"
    DELETED = "deleted"


class KnowledgeChunkVectorStatus(enum.Enum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeBaseType(enum.Enum):
    CLASSIC = "classic"
    LIGHTRAG = "lightrag"


KB_TYPE_ENUM = PGEnum(
    KnowledgeBaseType.CLASSIC.value,
    KnowledgeBaseType.LIGHTRAG.value,
    name="knowledge_base_kb_type",
    create_type=False,
)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    __table_args__ = (
        UniqueConstraint("enterprise_space_id", "name", name="uq_knowledge_base_space_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=KnowledgeBaseStatus.ACTIVE.value, nullable=False)
    kb_type: Mapped[str] = mapped_column(
        KB_TYPE_ENUM,
        default=KnowledgeBaseType.CLASSIC.value,
        nullable=False,
    )
    vector_db_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    graph_db_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"), nullable=True, index=True
    )
    default_chunk_size: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    default_chunk_overlap: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    default_retrieval_mode: Mapped[str] = mapped_column(String(20), default="hybrid", nullable=False)
    default_top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    default_score_threshold: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    milvus_collection_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # 创建时应由 resolve_knowledge_base_milvus_dimension 写入；1536 仅为 ORM/历史迁移占位。
    milvus_dimension: Mapped[int] = mapped_column(Integer, default=1536, nullable=False)
    milvus_metric_type: Mapped[str] = mapped_column(String(20), default="COSINE", nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    enterprise_space = relationship("EnterpriseSpace", backref="knowledge_bases")
    embedding_model = relationship("AIModel")
    neo4j_connection = relationship(
        "Neo4jConnection",
        back_populates="knowledge_base",
        uselist=False,
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, space_id={self.enterprise_space_id})>"


class Neo4jConnection(Base):
    __tablename__ = "neo4j_connection"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    uri: Mapped[str] = mapped_column(String(500), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    database: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="neo4j_connection")

    def __repr__(self) -> str:
        return f"<Neo4jConnection(kb_id={self.knowledge_base_id}, uri={self.uri})>"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_document"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "content_sha256", name="uq_document_kb_sha256"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(20), default="upload", nullable=False)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    storage_type: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_type: Mapped[str] = mapped_column(String(30), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=KnowledgeDocumentStatus.UPLOADED.value, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    parse_log_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chunking_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, kb_id={self.knowledge_base_id}, name={self.document_name})>"


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        UniqueConstraint("chunk_uid", name="uq_chunk_uid"),
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_preview: Mapped[str | None] = mapped_column(String(300), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keyword_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(keyword_text, ''))", persisted=True),
        nullable=False,
    )
    vector_status: Mapped[str] = mapped_column(
        String(20), default=KnowledgeChunkVectorStatus.PENDING.value, nullable=False
    )
    vector_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    knowledge_base = relationship("KnowledgeBase")
    document = relationship("KnowledgeDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"


class KbProcessBatchAction(enum.Enum):
    UPLOAD = "upload"
    PARSE = "parse"
    REINDEX = "reindex"
    DELETE = "delete"
    CANCEL = "cancel"


class KbProcessBatchStatus(enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class KbProcessBatchItemStatus(enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class KbProcessBatch(Base):
    __tablename__ = "kb_process_batch"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_uid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=KbProcessBatchStatus.RUNNING.value, nullable=False
    )
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User")
    knowledge_base = relationship("KnowledgeBase")
    items = relationship(
        "KbProcessBatchItem",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KbProcessBatch(id={self.id}, kb_id={self.knowledge_base_id}, action={self.action})>"


class KbProcessBatchItem(Base):
    __tablename__ = "kb_process_batch_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("kb_process_batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=KbProcessBatchItemStatus.RUNNING.value, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch = relationship("KbProcessBatch", back_populates="items")

    def __repr__(self) -> str:
        return f"<KbProcessBatchItem(id={self.id}, batch_id={self.batch_id}, file_name={self.file_name})>"
