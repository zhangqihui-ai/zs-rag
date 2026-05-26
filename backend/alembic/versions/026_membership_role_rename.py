"""rename membership role owner to space_admin

Revision ID: 026_membership_role_rename
Revises: 025_chat_lightrag_query_mode
Create Date: 2026-05-26

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "026_membership_role_rename"
down_revision: Union[str, None] = "025_chat_lightrag_query_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE membership SET role = 'space_admin' WHERE role = 'owner'")


def downgrade() -> None:
    op.execute("UPDATE membership SET role = 'owner' WHERE role = 'space_admin'")
