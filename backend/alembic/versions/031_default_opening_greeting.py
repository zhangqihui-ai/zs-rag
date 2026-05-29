"""backfill default opening greeting for conversations

Revision ID: 031_default_opening_greeting
Revises: 030_chat_model_param_toggles
Create Date: 2026-05-28

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031_default_opening_greeting"
down_revision: Union[str, None] = "030_chat_model_param_toggles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_OPENING_GREETING = "你好，我是你的智能助手，有什么需要帮助的吗？"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE chat_conversation SET opening_greeting = :greeting "
            "WHERE opening_greeting IS NULL"
        ).bindparams(greeting=DEFAULT_OPENING_GREETING)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE chat_conversation SET opening_greeting = NULL "
            "WHERE opening_greeting = :greeting"
        ).bindparams(greeting=DEFAULT_OPENING_GREETING)
    )
