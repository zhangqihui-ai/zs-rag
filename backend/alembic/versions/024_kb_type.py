"""Add knowledge_base.kb_type (classic | lightrag)

Revision ID: 024_kb_type
Revises: 023_kb_default_retrieval
Create Date: 2026-05-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024_kb_type"
down_revision: Union[str, None] = "023_kb_default_retrieval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KB_TYPE_ENUM = sa.Enum("classic", "lightrag", name="knowledge_base_kb_type")


def upgrade() -> None:
    _KB_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "knowledge_base",
        sa.Column(
            "kb_type",
            _KB_TYPE_ENUM,
            nullable=False,
            server_default="classic",
        ),
    )
    op.alter_column("knowledge_base", "kb_type", server_default=None)


def downgrade() -> None:
    op.drop_column("knowledge_base", "kb_type")
    _KB_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
