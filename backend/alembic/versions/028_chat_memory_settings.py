"""chat_conversation memory and dialog settings

Revision ID: 028_chat_memory_settings
Revises: 027_user_email_nullable
Create Date: 2026-05-28

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_chat_memory_settings"
down_revision: Union[str, None] = "027_user_email_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column(
            "max_history_messages",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("max_history_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chat_conversation",
        sa.Column(
            "refine_multiturn",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("opening_greeting", sa.Text(), nullable=True),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("empty_response", sa.Text(), nullable=True),
    )
    op.alter_column("chat_conversation", "max_history_messages", server_default=None)
    op.alter_column("chat_conversation", "refine_multiturn", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_conversation", "empty_response")
    op.drop_column("chat_conversation", "opening_greeting")
    op.drop_column("chat_conversation", "refine_multiturn")
    op.drop_column("chat_conversation", "max_history_tokens")
    op.drop_column("chat_conversation", "max_history_messages")
