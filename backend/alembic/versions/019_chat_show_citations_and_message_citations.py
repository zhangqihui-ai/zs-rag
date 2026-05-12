"""chat show_citations + chat_message.citations JSON

Revision ID: 019_chat_citations
Revises: 018_chat_system_prompt
Create Date: 2026-04-29

"""

import sqlalchemy as sa
from alembic import op

revision = "019_chat_citations"
down_revision = "018_chat_system_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("show_citations", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("chat_message", sa.Column("citations", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_message", "citations")
    op.drop_column("chat_conversation", "show_citations")
