"""chat_conversation and chat_session.conversation_id

Revision ID: 014_chat_conv
Revises: 052433bd5878
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "014_chat_conv"
down_revision = "052433bd5878"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_conversation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_space_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
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
        op.f("ix_chat_conversation_user_id"), "chat_conversation", ["user_id"], unique=False
    )

    op.add_column("chat_session", sa.Column("conversation_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_chat_session_conversation_id"), "chat_session", ["conversation_id"], unique=False
    )

    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, user_id, enterprise_space_id, title, created_at, updated_at FROM chat_session")).fetchall()
    for row in rows:
        sid, uid, esid, title, ca, ua = row
        conv_id = conn.execute(
            text(
                """
                INSERT INTO chat_conversation (user_id, enterprise_space_id, title, created_at, updated_at)
                VALUES (:uid, :esid, :title, :ca, :ua)
                RETURNING id
                """
            ),
            {"uid": uid, "esid": esid, "title": title, "ca": ca, "ua": ua},
        ).scalar_one()
        conn.execute(
            text("UPDATE chat_session SET conversation_id = :cid WHERE id = :sid"),
            {"cid": conv_id, "sid": sid},
        )

    op.alter_column("chat_session", "conversation_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_chat_session_conversation_id_chat_conversation"),
        "chat_session",
        "chat_conversation",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_chat_session_conversation_id_chat_conversation"), "chat_session", type_="foreignkey"
    )
    op.drop_index(op.f("ix_chat_session_conversation_id"), table_name="chat_session")
    op.drop_column("chat_session", "conversation_id")

    op.drop_index(op.f("ix_chat_conversation_user_id"), table_name="chat_conversation")
    op.drop_index(op.f("ix_chat_conversation_enterprise_space_id"), table_name="chat_conversation")
    op.drop_table("chat_conversation")
