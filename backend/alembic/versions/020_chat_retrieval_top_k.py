"""chat_conversation.retrieval_top_k for merge limit

Revision ID: 020_chat_retrieval_top_k
Revises: 019_chat_citations
Create Date: 2026-04-24

"""

import sqlalchemy as sa
from alembic import op

revision = "020_chat_retrieval_top_k"
down_revision = "019_chat_citations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column(
            "retrieval_top_k",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "retrieval_top_k")
