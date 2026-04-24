"""Set knowledge_base default chunking to 512/50

Revision ID: 013_kb_default_chunk_512_50
Revises: 012_rename_del_kb
Create Date: 2026-04-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_kb_default_chunk_512_50"
down_revision: Union[str, None] = "012_rename_del_kb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 经试用后发现 1024 对中文技术/公文类文档切块过粗，小文档常出现"全文一个块"。
    # 调整默认为 512/50：更容易对齐章节/段落边界，召回片段更聚焦。
    op.alter_column("knowledge_base", "default_chunk_size", server_default=sa.text("512"))
    op.alter_column("knowledge_base", "default_chunk_overlap", server_default=sa.text("50"))


def downgrade() -> None:
    op.alter_column("knowledge_base", "default_chunk_size", server_default=sa.text("1024"))
    op.alter_column("knowledge_base", "default_chunk_overlap", server_default=sa.text("50"))
