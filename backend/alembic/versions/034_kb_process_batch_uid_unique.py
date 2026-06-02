"""kb_process_batch batch_uid unique per knowledge base

Revision ID: 034_kb_process_batch_uid_unique
Revises: 033_kb_process_audit
Create Date: 2026-06-02

"""

from __future__ import annotations

from alembic import op

revision = "034_kb_process_batch_uid_unique"
down_revision = "033_kb_process_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 合并并发批量操作产生的重复 batch_uid（保留最早一条）
    op.execute(
        """
        DELETE FROM kb_process_batch_item
        WHERE batch_id IN (
            SELECT b.id
            FROM kb_process_batch b
            WHERE EXISTS (
                SELECT 1
                FROM kb_process_batch keeper
                WHERE keeper.enterprise_space_id = b.enterprise_space_id
                  AND keeper.knowledge_base_id = b.knowledge_base_id
                  AND keeper.batch_uid = b.batch_uid
                  AND keeper.id < b.id
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM kb_process_batch b
        WHERE EXISTS (
            SELECT 1
            FROM kb_process_batch keeper
            WHERE keeper.enterprise_space_id = b.enterprise_space_id
              AND keeper.knowledge_base_id = b.knowledge_base_id
              AND keeper.batch_uid = b.batch_uid
              AND keeper.id < b.id
        )
        """
    )
    op.create_index(
        "uq_kb_process_batch_space_kb_uid",
        "kb_process_batch",
        ["enterprise_space_id", "knowledge_base_id", "batch_uid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_kb_process_batch_space_kb_uid", table_name="kb_process_batch")
