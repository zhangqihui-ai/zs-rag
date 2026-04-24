"""Rename deleted knowledge bases to free unique names

Revision ID: 012_rename_del_kb
Revises: 011_kb_default_chunk_1024_50
Create Date: 2026-04-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_rename_del_kb"
down_revision: Union[str, None] = "011_kb_default_chunk_1024_50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 软删除的知识库会阻塞同名新建（唯一约束 enterprise_space_id + name）。
    # 这里为历史数据补齐归档后缀，释放原始名称。
    bind = op.get_bind()
    now = "19700101000000"
    try:
        now = bind.execute(sa.text("SELECT to_char(now() at time zone 'utc','YYYYMMDDHH24MISS')")).scalar() or now
    except Exception:
        pass

    prefix = "__deleted__"
    rows = bind.execute(
        sa.text("SELECT id, name FROM knowledge_base WHERE status='deleted' AND name NOT LIKE :like_prefix"),
        {"like_prefix": f"%{prefix}%"},
    ).fetchall()
    for kb_id, original in rows:
        suffix = f"{prefix}{kb_id}__{now}"
        keep = 200 - len(suffix)
        base = (original or "knowledge_base")[: max(keep, 0)]
        new_name = (base + suffix)[-200:]
        bind.execute(
            sa.text("UPDATE knowledge_base SET name=:name WHERE id=:id"),
            {"name": new_name, "id": kb_id},
        )


def downgrade() -> None:
    # 不回滚名称变更（避免重新引入唯一约束冲突）
    pass

