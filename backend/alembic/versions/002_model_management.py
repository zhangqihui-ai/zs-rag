"""Add provider_config and model_ref tables

Revision ID: 002_model_management
Revises: 001_initial
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_model_management'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create provider_config table
    op.create_table(
        'provider_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_space_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('provider_type', sa.String(length=50), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('api_key', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=30),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_space_id'], ['enterprise_space.id'], ondelete='CASCADE', name='fk_provider_config_enterprise_space_id_enterprise_space'),
        sa.PrimaryKeyConstraint('id', name='pk_provider_config'),
    )
    op.create_index('ix_provider_config_enterprise_space_id', 'provider_config', ['enterprise_space_id'], unique=False)

    # Create model_ref table
    op.create_table(
        'model_ref',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_space_id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('default_params', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_space_id'], ['enterprise_space.id'], ondelete='CASCADE', name='fk_model_ref_enterprise_space_id_enterprise_space'),
        sa.ForeignKeyConstraint(['provider_id'], ['provider_config.id'], ondelete='CASCADE', name='fk_model_ref_provider_id_provider_config'),
        sa.PrimaryKeyConstraint('id', name='pk_model_ref'),
    )
    op.create_index('ix_model_ref_enterprise_space_id', 'model_ref', ['enterprise_space_id'], unique=False)
    op.create_index('ix_model_ref_provider_id', 'model_ref', ['provider_id'], unique=False)


def downgrade() -> None:
    op.drop_table('model_ref')
    op.drop_table('provider_config')
