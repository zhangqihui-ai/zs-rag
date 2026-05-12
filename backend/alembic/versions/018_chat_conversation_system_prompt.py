"""chat_conversation.system_prompt — 对话级系统提示词

Revision ID: 018_chat_system_prompt
Revises: 017_chat_llm_model_fk
Create Date: 2026-04-24

"""

import sqlalchemy as sa
from alembic import op

revision = "018_chat_system_prompt"
down_revision = "017_chat_llm_model_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("system_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "system_prompt")
