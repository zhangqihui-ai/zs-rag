"""知识库默认检索：向量权重 0.3、Score 阈值 0.5

Revision ID: 023_kb_default_retrieval
Revises: 022_chat_embed_conversation
Create Date: 2026-05-21

"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_kb_default_retrieval"
down_revision: Union[str, None] = "022_chat_embed_conversation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RETRIEVAL_PATCH = {
    "vector_weight": 0.3,
    "hybrid_strategy": "weight",
    "score_threshold_enabled": True,
}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, config FROM knowledge_base WHERE status != 'deleted'"
        )
    ).fetchall()

    for row in rows:
        kb_id = row[0]
        raw_config = row[1]
        config = dict(raw_config) if isinstance(raw_config, dict) else {}
        retrieval = dict(config.get("retrieval") or {})
        retrieval.update(_RETRIEVAL_PATCH)
        config["retrieval"] = retrieval
        conn.execute(
            sa.text(
                """
                UPDATE knowledge_base
                SET default_score_threshold = :threshold,
                    config = CAST(:config AS jsonb)
                WHERE id = :kb_id
                """
            ),
            {
                "kb_id": kb_id,
                "threshold": 0.5,
                "config": json.dumps(config, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE knowledge_base
            SET default_score_threshold = NULL
            WHERE status != 'deleted'
            """
        )
    )
