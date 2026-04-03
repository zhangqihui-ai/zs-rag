"""Add enterprise_space, user, membership tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enterprise_space table
    op.create_table(
        'enterprise_space',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_enterprise_space'),
        sa.UniqueConstraint('name', name='uq_enterprise_space_name'),
        sa.UniqueConstraint('slug', name='uq_enterprise_space_slug'),
    )
    op.create_index('ix_enterprise_space_name', 'enterprise_space', ['name'], unique=False)
    op.create_index('ix_enterprise_space_slug', 'enterprise_space', ['slug'], unique=False)

    # Create user table
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_user'),
        sa.UniqueConstraint('email', name='uq_user_email'),
        sa.UniqueConstraint('username', name='uq_user_username'),
    )
    op.create_index('ix_user_email', 'user', ['email'], unique=False)
    op.create_index('ix_user_username', 'user', ['username'], unique=False)

    # Create membership table
    op.create_table(
        'membership',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enterprise_space_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_membership'),
        sa.ForeignKeyConstraint(['enterprise_space_id'], ['enterprise_space.id'], ondelete='CASCADE', name='fk_membership_enterprise_space_id_enterprise_space'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE', name='fk_membership_user_id_user'),
        sa.UniqueConstraint('user_id', 'enterprise_space_id', name='uq_membership_user_space'),
    )


def downgrade() -> None:
    op.drop_table('membership')
    op.drop_table('user')
    op.drop_table('enterprise_space')
