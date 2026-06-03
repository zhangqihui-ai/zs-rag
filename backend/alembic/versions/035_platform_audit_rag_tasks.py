"""platform audit + rag evaluation + document background task tables

Revision ID: 035_platform_audit_rag_tasks
Revises: 034_kb_process_batch_uid_unique
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "035_platform_audit_rag_tasks"
down_revision = "034_kb_process_batch_uid_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_audit_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_audit_event_action", "platform_audit_event", ["action"])
    op.create_index("ix_platform_audit_event_resource_type", "platform_audit_event", ["resource_type"])
    op.create_index("ix_platform_audit_event_request_id", "platform_audit_event", ["request_id"])
    op.create_index("ix_platform_audit_event_created_at", "platform_audit_event", ["created_at"])
    op.create_index("ix_platform_audit_event_enterprise_space_id", "platform_audit_event", ["enterprise_space_id"])
    op.create_index("ix_platform_audit_event_user_id", "platform_audit_event", ["user_id"])

    op.create_table(
        "rag_benchmark",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("knowledge_base_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_benchmark_enterprise_space_id", "rag_benchmark", ["enterprise_space_id"])

    op.create_table(
        "rag_benchmark_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["benchmark_id"], ["rag_benchmark.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_benchmark_item_benchmark_id", "rag_benchmark_item", ["benchmark_id"])

    op.create_table(
        "rag_evaluation_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("retrieval_config", sa.JSON(), nullable=True),
        sa.Column("started_by_user_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["benchmark_id"], ["rag_benchmark.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_evaluation_run_benchmark_id", "rag_evaluation_run", ["benchmark_id"])
    op.create_index("ix_rag_evaluation_run_enterprise_space_id", "rag_evaluation_run", ["enterprise_space_id"])

    op.create_table(
        "rag_evaluation_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("benchmark_item_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["benchmark_item_id"], ["rag_benchmark_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["rag_evaluation_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_evaluation_result_run_id", "rag_evaluation_result", ["run_id"])
    op.create_index("ix_rag_evaluation_result_benchmark_item_id", "rag_evaluation_result", ["benchmark_item_id"])

    op.create_table(
        "document_background_task",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_uid", sa.String(length=64), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_uid"),
    )
    op.create_index("ix_document_background_task_task_uid", "document_background_task", ["task_uid"])
    op.create_index("ix_document_background_task_status", "document_background_task", ["status"])
    op.create_index("ix_document_background_task_document_id", "document_background_task", ["document_id"])


def downgrade() -> None:
    op.drop_table("document_background_task")
    op.drop_table("rag_evaluation_result")
    op.drop_table("rag_evaluation_run")
    op.drop_table("rag_benchmark_item")
    op.drop_table("rag_benchmark")
    op.drop_table("platform_audit_event")
