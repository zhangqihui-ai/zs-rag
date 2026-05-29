"""chat_conversation model sampling param enable toggles

Revision ID: 030_chat_model_param_toggles
Revises: 029_chat_suggest_next_questions
Create Date: 2026-05-28

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_chat_model_param_toggles"
down_revision: Union[str, None] = "029_chat_suggest_next_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("temperature_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("max_tokens_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("top_p_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("chat_conversation", "temperature_enabled", server_default=None)
    op.alter_column("chat_conversation", "max_tokens_enabled", server_default=None)
    op.alter_column("chat_conversation", "top_p_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_conversation", "top_p_enabled")
    op.drop_column("chat_conversation", "max_tokens_enabled")
    op.drop_column("chat_conversation", "temperature_enabled")
