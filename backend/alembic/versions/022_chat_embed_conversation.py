"""chat_embed_api_key.conversation_id — 按对话签发嵌入密钥

Revision ID: 022_chat_embed_conversation
Revises: 021_chat_embed_api_key
Create Date: 2026-05-15

"""

import sqlalchemy as sa
from alembic import op

revision = "022_chat_embed_conversation"
down_revision = "021_chat_embed_api_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_embed_api_key",
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_chat_embed_api_key_conversation_id",
        "chat_embed_api_key",
        ["conversation_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_chat_embed_api_key_conversation_id",
        "chat_embed_api_key",
        "chat_conversation",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_embed_api_key_conversation_id", "chat_embed_api_key", type_="foreignkey")
    op.drop_index("ix_chat_embed_api_key_conversation_id", table_name="chat_embed_api_key")
    op.drop_column("chat_embed_api_key", "conversation_id")
