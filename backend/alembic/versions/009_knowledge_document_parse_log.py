"""Add parse_log_json to knowledge_document for persisted parse/reindex logs

Revision ID: 009_doc_parse_log
Revises: 008_remove_milvus_cfg
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_doc_parse_log"
down_revision: Union[str, None] = "008_remove_milvus_cfg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_document", sa.Column("parse_log_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_document", "parse_log_json")
