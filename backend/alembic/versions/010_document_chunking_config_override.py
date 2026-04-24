"""Add document-level chunking config override

Revision ID: 010_doc_chunking_override
Revises: 009_doc_parse_log
Create Date: 2026-04-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_doc_chunking_override"
down_revision: Union[str, None] = "009_doc_parse_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_document", sa.Column("chunking_config_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_document", "chunking_config_json")

