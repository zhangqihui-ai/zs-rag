"""add platform_usage_event table

Revision ID: 037_platform_usage_event
Revises: 036_chat_rag_mode
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "037_platform_usage_event"
down_revision = "036_chat_rag_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_usage_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("model_type", sa.String(length=20), nullable=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["ai_model.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_usage_event_enterprise_space_id", "platform_usage_event", ["enterprise_space_id"])
    op.create_index("ix_platform_usage_event_event_type", "platform_usage_event", ["event_type"])
    op.create_index("ix_platform_usage_event_model_id", "platform_usage_event", ["model_id"])
    op.create_index("ix_platform_usage_event_knowledge_base_id", "platform_usage_event", ["knowledge_base_id"])
    op.create_index("ix_platform_usage_event_user_id", "platform_usage_event", ["user_id"])
    op.create_index("ix_platform_usage_event_created_at", "platform_usage_event", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_usage_event_created_at", table_name="platform_usage_event")
    op.drop_index("ix_platform_usage_event_user_id", table_name="platform_usage_event")
    op.drop_index("ix_platform_usage_event_knowledge_base_id", table_name="platform_usage_event")
    op.drop_index("ix_platform_usage_event_model_id", table_name="platform_usage_event")
    op.drop_index("ix_platform_usage_event_event_type", table_name="platform_usage_event")
    op.drop_index("ix_platform_usage_event_enterprise_space_id", table_name="platform_usage_event")
    op.drop_table("platform_usage_event")
