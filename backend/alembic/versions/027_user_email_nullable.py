"""user email nullable

Revision ID: 027_user_email_nullable
Revises: 026_membership_role_rename
Create Date: 2026-05-26

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_user_email_nullable"
down_revision: Union[str, None] = "026_membership_role_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("user", "email", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE \"user\" SET email = username || '@local.invalid' WHERE email IS NULL")
    op.alter_column("user", "email", existing_type=sa.String(length=255), nullable=False)
