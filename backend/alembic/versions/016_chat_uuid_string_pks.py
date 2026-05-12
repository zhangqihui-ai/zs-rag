"""Chat tables: string UUID PKs; merge chat_configuration into chat_conversation.

Destructive migration: drops existing chat_message, chat_configuration, chat_session,
chat_conversation and recreates with new schema. All chat data is lost.

Revision ID: 016_chat_uuid
Revises: 015_cfg_conv
Create Date: 2026-04-24

"""

import sqlalchemy as sa
from alembic import op

revision = "016_chat_uuid"
down_revision = "015_cfg_conv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("chat_message")
    op.drop_table("chat_configuration")
    op.drop_table("chat_session")
    op.drop_table("chat_conversation")

    op.create_table(
        "chat_conversation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("model_provider", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=150), nullable=True),
        sa.Column("knowledge_base_ids", sa.JSON(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("top_p", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["enterprise_space_id"],
            ["enterprise_space.id"],
            name=op.f("fk_chat_conversation_enterprise_space_id_enterprise_space"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_chat_conversation_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversation")),
    )
    op.create_index(
        op.f("ix_chat_conversation_enterprise_space_id"),
        "chat_conversation",
        ["enterprise_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_conversation_user_id"),
        "chat_conversation",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "chat_session",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversation.id"],
            name=op.f("fk_chat_session_conversation_id_chat_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["enterprise_space_id"],
            ["enterprise_space.id"],
            name=op.f("fk_chat_session_enterprise_space_id_enterprise_space"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_chat_session_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_session")),
    )
    op.create_index(
        op.f("ix_chat_session_conversation_id"),
        "chat_session",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_session_enterprise_space_id"),
        "chat_session",
        ["enterprise_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_session_user_id"), "chat_session", ["user_id"], unique=False
    )

    op.create_table(
        "chat_message",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_session.id"],
            name=op.f("fk_chat_message_session_id_chat_session"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_message")),
    )
    op.create_index(
        op.f("ix_chat_message_session_id"), "chat_message", ["session_id"], unique=False
    )


def downgrade() -> None:
    raise NotImplementedError("016_chat_uuid upgrade is destructive; downgrade not supported")
