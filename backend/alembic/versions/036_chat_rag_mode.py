"""add chat rag_mode and agent_trace

Revision ID: 036_chat_rag_mode
Revises: 035_platform_audit_rag_tasks
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "036_chat_rag_mode"
down_revision = "035_platform_audit_rag_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("rag_mode", sa.String(length=20), nullable=False, server_default="classic"),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("agentic_max_iterations", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("agentic_min_relevant_docs", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("chat_message", sa.Column("agent_trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_message", "agent_trace")
    op.drop_column("chat_conversation", "agentic_min_relevant_docs")
    op.drop_column("chat_conversation", "agentic_max_iterations")
    op.drop_column("chat_conversation", "rag_mode")
