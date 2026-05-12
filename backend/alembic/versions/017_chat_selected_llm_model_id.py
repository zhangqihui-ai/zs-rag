"""chat_conversation.selected_llm_model_id — 唯一绑定 ai_model，消除同 provider_code 多接入歧义

Revision ID: 017_chat_llm_model_fk
Revises: 016_chat_uuid
Create Date: 2026-04-28

"""

import sqlalchemy as sa
from alembic import op

revision = "017_chat_llm_model_fk"
down_revision = "016_chat_uuid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("selected_llm_model_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_chat_conversation_selected_llm_model_id"),
        "chat_conversation",
        ["selected_llm_model_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_chat_conversation_selected_llm_model_id_ai_model"),
        "chat_conversation",
        "ai_model",
        ["selected_llm_model_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_chat_conversation_selected_llm_model_id_ai_model"),
        "chat_conversation",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_chat_conversation_selected_llm_model_id"), table_name="chat_conversation")
    op.drop_column("chat_conversation", "selected_llm_model_id")
