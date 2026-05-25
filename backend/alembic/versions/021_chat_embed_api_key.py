"""chat_embed_api_key for iframe embed Bearer auth

Revision ID: 021_chat_embed_api_key
Revises: 020_chat_retrieval_top_k
Create Date: 2026-05-15

"""

import sqlalchemy as sa
from alembic import op

revision = "021_chat_embed_api_key"
down_revision = "020_chat_retrieval_top_k"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_embed_api_key",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_space_id"], ["enterprise_space.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_chat_embed_api_key_enterprise_space_id",
        "chat_embed_api_key",
        ["enterprise_space_id"],
        unique=False,
    )
    op.create_index(
        "ix_chat_embed_api_key_created_by_user_id",
        "chat_embed_api_key",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_embed_api_key_created_by_user_id", table_name="chat_embed_api_key")
    op.drop_index("ix_chat_embed_api_key_enterprise_space_id", table_name="chat_embed_api_key")
    op.drop_table("chat_embed_api_key")
