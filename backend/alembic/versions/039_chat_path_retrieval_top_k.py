"""add vector/lightrag path retrieval top_k to chat_conversation

Revision ID: 039_chat_path_retrieval_top_k
Revises: 038_agentic_context_user_turns
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "039_chat_path_retrieval_top_k"
down_revision = "038_agentic_context_user_turns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("vector_retrieval_top_k", sa.Integer(), nullable=False, server_default="8"),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("lightrag_retrieval_top_k", sa.Integer(), nullable=False, server_default="8"),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "lightrag_retrieval_top_k")
    op.drop_column("chat_conversation", "vector_retrieval_top_k")
