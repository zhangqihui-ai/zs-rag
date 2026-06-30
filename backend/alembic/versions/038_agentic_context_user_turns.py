"""add agentic_context_user_turns to chat_conversation

Revision ID: 038_agentic_context_user_turns
Revises: 037_platform_usage_event
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "038_agentic_context_user_turns"
down_revision = "037_platform_usage_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("agentic_context_user_turns", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "agentic_context_user_turns")
