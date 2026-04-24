"""Set knowledge_base default chunking to 1024/50

Revision ID: 011_kb_default_chunk_1024_50
Revises: 010_doc_chunking_override
Create Date: 2026-04-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_kb_default_chunk_1024_50"
down_revision: Union[str, None] = "010_doc_chunking_override"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("knowledge_base", "default_chunk_size", server_default=sa.text("1024"))
    op.alter_column("knowledge_base", "default_chunk_overlap", server_default=sa.text("50"))


def downgrade() -> None:
    op.alter_column("knowledge_base", "default_chunk_size", server_default=sa.text("500"))
    op.alter_column("knowledge_base", "default_chunk_overlap", server_default=sa.text("80"))

