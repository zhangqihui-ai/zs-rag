"""chat_conversation suggest next questions settings

Revision ID: 029_chat_suggest_next_questions
Revises: 028_chat_memory_settings
Create Date: 2026-05-28

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_chat_suggest_next_questions"
down_revision: Union[str, None] = "028_chat_memory_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column(
            "suggest_next_questions_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "chat_conversation",
        sa.Column(
            "suggest_next_questions_model_id",
            sa.Integer(),
            sa.ForeignKey("ai_model.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "chat_conversation",
        sa.Column(
            "suggest_next_questions_prompt_mode",
            sa.String(length=20),
            nullable=False,
            server_default="system",
        ),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("suggest_next_questions_custom_prompt", sa.Text(), nullable=True),
    )
    op.alter_column("chat_conversation", "suggest_next_questions_enabled", server_default=None)
    op.alter_column("chat_conversation", "suggest_next_questions_prompt_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_conversation", "suggest_next_questions_custom_prompt")
    op.drop_column("chat_conversation", "suggest_next_questions_prompt_mode")
    op.drop_column("chat_conversation", "suggest_next_questions_model_id")
    op.drop_column("chat_conversation", "suggest_next_questions_enabled")
