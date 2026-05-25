"""chat_conversation.lightrag_query_mode

Revision ID: 025_chat_lightrag_query_mode
Revises: 024_kb_type
Create Date: 2026-05-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_chat_lightrag_query_mode"
down_revision: Union[str, None] = "024_kb_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column(
            "lightrag_query_mode",
            sa.String(length=20),
            nullable=False,
            server_default="mix",
        ),
    )
    op.alter_column("chat_conversation", "lightrag_query_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_conversation", "lightrag_query_mode")
