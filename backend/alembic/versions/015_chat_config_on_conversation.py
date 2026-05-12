"""Bind chat_configuration to chat_conversation (one per dialog)

Revision ID: 015_cfg_conv
Revises: 014_chat_conv
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "015_cfg_conv"
down_revision = "014_chat_conv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_configuration", sa.Column("conversation_id", sa.Integer(), nullable=True))
    op.execute(
        text(
            """
            UPDATE chat_configuration AS c
            SET conversation_id = s.conversation_id
            FROM chat_session AS s
            WHERE c.session_id = s.id
            """
        )
    )
    op.execute(
        text(
            """
            DELETE FROM chat_configuration AS c1
            USING chat_configuration AS c2
            WHERE c1.conversation_id IS NOT NULL
              AND c2.conversation_id IS NOT NULL
              AND c1.conversation_id = c2.conversation_id
              AND c1.id > c2.id
            """
        )
    )
    op.alter_column("chat_configuration", "conversation_id", nullable=False)

    op.drop_constraint("fk_chat_configuration_session_id_chat_session", "chat_configuration", type_="foreignkey")
    op.drop_constraint("uq_chat_configuration_session_id", "chat_configuration", type_="unique")
    op.drop_column("chat_configuration", "session_id")

    op.create_foreign_key(
        op.f("fk_chat_configuration_conversation_id_chat_conversation"),
        "chat_configuration",
        "chat_conversation",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_chat_configuration_conversation_id"), "chat_configuration", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_chat_configuration_conversation_id"), "chat_configuration", type_="unique")
    op.drop_constraint(
        op.f("fk_chat_configuration_conversation_id_chat_conversation"), "chat_configuration", type_="foreignkey"
    )
    op.add_column("chat_configuration", sa.Column("session_id", sa.Integer(), nullable=True))
    op.execute(
        text(
            """
            UPDATE chat_configuration AS c
            SET session_id = (
                SELECT s.id FROM chat_session s
                WHERE s.conversation_id = c.conversation_id
                ORDER BY s.id ASC
                LIMIT 1
            )
            """
        )
    )
    op.alter_column("chat_configuration", "session_id", nullable=False)
    op.create_foreign_key(
        "fk_chat_configuration_session_id_chat_session",
        "chat_configuration",
        "chat_session",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_chat_configuration_session_id", "chat_configuration", ["session_id"])
    op.drop_column("chat_configuration", "conversation_id")
