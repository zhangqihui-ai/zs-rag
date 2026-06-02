"""add chat_conversation.lightrag_chunk_top_k

Revision ID: 032_chat_lightrag_chunk_top_k
Revises: 031_default_opening_greeting
Create Date: 2026-06-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032_chat_lightrag_chunk_top_k"
down_revision: Union[str, None] = "031_default_opening_greeting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("lightrag_chunk_top_k", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "lightrag_chunk_top_k")
