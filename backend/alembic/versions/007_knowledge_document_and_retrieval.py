"""Add knowledge documents, chunks, and retrieval config fields

Revision ID: 007_knowledge_document_and_retrieval
Revises: 006_kb_milvus_config_rename
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "007_kb_documents_retrieval"
down_revision: Union[str, None] = "006_kb_milvus_config_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_base", sa.Column("embedding_model_id", sa.Integer(), nullable=True))
    op.add_column("knowledge_base", sa.Column("default_chunk_size", sa.Integer(), nullable=False, server_default="500"))
    op.add_column("knowledge_base", sa.Column("default_chunk_overlap", sa.Integer(), nullable=False, server_default="80"))
    op.add_column("knowledge_base", sa.Column("default_retrieval_mode", sa.String(length=20), nullable=False, server_default="hybrid"))
    op.add_column("knowledge_base", sa.Column("default_top_k", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("knowledge_base", sa.Column("default_score_threshold", sa.Numeric(10, 6), nullable=True))
    op.create_foreign_key(
        "fk_knowledge_base_embedding_model_id_ai_model",
        "knowledge_base",
        "ai_model",
        ["embedding_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_knowledge_base_embedding_model_id", "knowledge_base", ["embedding_model_id"], unique=False)
    op.create_index("idx_knowledge_base_space_status", "knowledge_base", ["enterprise_space_id", "status"], unique=False)
    op.create_unique_constraint("uq_knowledge_base_space_name", "knowledge_base", ["enterprise_space_id", "name"])
    op.alter_column("knowledge_base", "default_chunk_size", server_default=None)
    op.alter_column("knowledge_base", "default_chunk_overlap", server_default=None)
    op.alter_column("knowledge_base", "default_retrieval_mode", server_default=None)
    op.alter_column("knowledge_base", "default_top_k", server_default=None)

    op.execute(
        """
        UPDATE knowledge_milvus_config kmc
        SET collection_name = CONCAT('kb_', kb.enterprise_space_id, '_', kb.id, '_chunks')
        FROM knowledge_base kb
        WHERE kmc.knowledge_base_id = kb.id
          AND (kmc.collection_name IS NULL OR kmc.collection_name = '')
        """
    )
    op.alter_column("knowledge_milvus_config", "collection_name", existing_type=sa.String(length=200), nullable=False)

    op.create_table(
        "knowledge_document",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="upload"),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=20), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("storage_type", sa.String(length=20), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("parser_type", sa.String(length=30), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="uploaded"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_document"),
        sa.UniqueConstraint("knowledge_base_id", "content_sha256", name="uq_document_kb_sha256"),
    )
    op.create_index("idx_document_space_kb_status", "knowledge_document", ["enterprise_space_id", "knowledge_base_id", "status"], unique=False)
    op.create_index("idx_document_kb_created_at", "knowledge_document", ["knowledge_base_id", "created_at"], unique=False)
    op.create_index("ix_knowledge_document_enterprise_space_id", "knowledge_document", ["enterprise_space_id"], unique=False)
    op.create_index("ix_knowledge_document_knowledge_base_id", "knowledge_document", ["knowledge_base_id"], unique=False)
    op.alter_column("knowledge_document", "source_type", server_default=None)
    op.alter_column("knowledge_document", "storage_type", server_default=None)
    op.alter_column("knowledge_document", "status", server_default=None)
    op.alter_column("knowledge_document", "chunk_count", server_default=None)

    op.create_table(
        "knowledge_chunk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_uid", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_preview", sa.String(length=300), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.String(length=500), nullable=True),
        sa.Column("keyword_text", sa.Text(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(keyword_text, ''))", persisted=True),
            nullable=False,
        ),
        sa.Column("vector_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("vector_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_chunk"),
        sa.UniqueConstraint("chunk_uid", name="uq_chunk_uid"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )
    op.create_index("idx_chunk_kb_document", "knowledge_chunk", ["knowledge_base_id", "document_id"], unique=False)
    op.create_index("idx_chunk_kb_vector_status", "knowledge_chunk", ["knowledge_base_id", "vector_status"], unique=False)
    op.create_index("gin_chunk_search_vector", "knowledge_chunk", ["search_vector"], unique=False, postgresql_using="gin")
    op.create_index("ix_knowledge_chunk_enterprise_space_id", "knowledge_chunk", ["enterprise_space_id"], unique=False)
    op.create_index("ix_knowledge_chunk_knowledge_base_id", "knowledge_chunk", ["knowledge_base_id"], unique=False)
    op.create_index("ix_knowledge_chunk_document_id", "knowledge_chunk", ["document_id"], unique=False)
    op.alter_column("knowledge_chunk", "vector_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunk_document_id", table_name="knowledge_chunk")
    op.drop_index("ix_knowledge_chunk_knowledge_base_id", table_name="knowledge_chunk")
    op.drop_index("ix_knowledge_chunk_enterprise_space_id", table_name="knowledge_chunk")
    op.drop_index("gin_chunk_search_vector", table_name="knowledge_chunk")
    op.drop_index("idx_chunk_kb_vector_status", table_name="knowledge_chunk")
    op.drop_index("idx_chunk_kb_document", table_name="knowledge_chunk")
    op.drop_table("knowledge_chunk")

    op.drop_index("ix_knowledge_document_knowledge_base_id", table_name="knowledge_document")
    op.drop_index("ix_knowledge_document_enterprise_space_id", table_name="knowledge_document")
    op.drop_index("idx_document_kb_created_at", table_name="knowledge_document")
    op.drop_index("idx_document_space_kb_status", table_name="knowledge_document")
    op.drop_table("knowledge_document")

    op.alter_column("knowledge_milvus_config", "collection_name", existing_type=sa.String(length=200), nullable=True)

    op.drop_constraint("uq_knowledge_base_space_name", "knowledge_base", type_="unique")
    op.drop_index("idx_knowledge_base_space_status", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_embedding_model_id", table_name="knowledge_base")
    op.drop_constraint("fk_knowledge_base_embedding_model_id_ai_model", "knowledge_base", type_="foreignkey")
    op.drop_column("knowledge_base", "default_score_threshold")
    op.drop_column("knowledge_base", "default_top_k")
    op.drop_column("knowledge_base", "default_retrieval_mode")
    op.drop_column("knowledge_base", "default_chunk_overlap")
    op.drop_column("knowledge_base", "default_chunk_size")
    op.drop_column("knowledge_base", "embedding_model_id")
