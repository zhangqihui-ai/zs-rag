"""add kb_process_batch audit tables

Revision ID: 033_kb_process_audit
Revises: 032_chat_lightrag_chunk_top_k
Create Date: 2026-06-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033_kb_process_audit"
down_revision: Union[str, None] = "032_chat_lightrag_chunk_top_k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kb_process_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_uid", sa.String(length=64), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_process_batch_batch_uid", "kb_process_batch", ["batch_uid"])
    op.create_index("ix_kb_process_batch_enterprise_space_id", "kb_process_batch", ["enterprise_space_id"])
    op.create_index("ix_kb_process_batch_knowledge_base_id", "kb_process_batch", ["knowledge_base_id"])
    op.create_index("ix_kb_process_batch_user_id", "kb_process_batch", ["user_id"])
    op.create_index("ix_kb_process_batch_started_at", "kb_process_batch", ["started_at"])
    op.create_index(
        "ix_kb_process_batch_kb_started",
        "kb_process_batch",
        ["knowledge_base_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "kb_process_batch_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["kb_process_batch.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_process_batch_item_batch_id", "kb_process_batch_item", ["batch_id"])
    op.create_index("ix_kb_process_batch_item_document_id", "kb_process_batch_item", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_kb_process_batch_item_document_id", table_name="kb_process_batch_item")
    op.drop_index("ix_kb_process_batch_item_batch_id", table_name="kb_process_batch_item")
    op.drop_table("kb_process_batch_item")
    op.drop_index("ix_kb_process_batch_kb_started", table_name="kb_process_batch")
    op.drop_index("ix_kb_process_batch_started_at", table_name="kb_process_batch")
    op.drop_index("ix_kb_process_batch_user_id", table_name="kb_process_batch")
    op.drop_index("ix_kb_process_batch_knowledge_base_id", table_name="kb_process_batch")
    op.drop_index("ix_kb_process_batch_enterprise_space_id", table_name="kb_process_batch")
    op.drop_index("ix_kb_process_batch_batch_uid", table_name="kb_process_batch")
    op.drop_table("kb_process_batch")
