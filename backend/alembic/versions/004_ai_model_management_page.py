"""Align model management schema with model center page design

Revision ID: 004_ai_model_management_page
Revises: 003_knowledge_base
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_ai_model_management_page'
down_revision: Union[str, None] = '003_knowledge_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column('provider_config', sa.Column('deployment_type', sa.String(length=20), nullable=False, server_default='public'))
    op.add_column('provider_config', sa.Column('supported_types', sa.JSON(), nullable=True))
    op.add_column('provider_config', sa.Column('sync_status', sa.String(length=20), nullable=False, server_default='pending'))
    op.add_column('provider_config', sa.Column('last_sync_at', sa.DateTime(), nullable=True))
    op.add_column('provider_config', sa.Column('last_sync_error', sa.String(length=500), nullable=True))

    op.add_column('model_ref', sa.Column('model_code', sa.String(length=200), nullable=True))
    op.add_column('model_ref', sa.Column('model_type', sa.String(length=30), nullable=False, server_default='llm'))
    op.add_column('model_ref', sa.Column('context_window', sa.Integer(), nullable=True))
    op.add_column('model_ref', sa.Column('max_output_tokens', sa.Integer(), nullable=True))
    op.add_column('model_ref', sa.Column('raw_payload', sa.JSON(), nullable=True))

    op.execute("UPDATE model_ref SET model_code = model_name WHERE model_code IS NULL")
    op.alter_column('model_ref', 'model_code', existing_type=sa.String(length=200), nullable=False)

    op.create_unique_constraint(
        'uq_provider_config_space_name_base_url',
        'provider_config',
        ['enterprise_space_id', 'name', 'base_url'],
    )
    op.create_unique_constraint(
        'uq_model_ref_provider_model_code',
        'model_ref',
        ['provider_id', 'model_code'],
    )

    op.create_table(
        'model_default',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_space_id', sa.Integer(), nullable=False),
        sa.Column('model_type', sa.String(length=30), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_space_id'], ['enterprise_space.id'], ondelete='CASCADE', name='fk_model_default_enterprise_space_id_enterprise_space'),
        sa.ForeignKeyConstraint(['model_id'], ['model_ref.id'], ondelete='CASCADE', name='fk_model_default_model_id_model_ref'),
        sa.PrimaryKeyConstraint('id', name='pk_model_default'),
        sa.UniqueConstraint('enterprise_space_id', 'model_type', name='uq_model_default_space_model_type'),
    )
    op.create_index('ix_model_default_enterprise_space_id', 'model_default', ['enterprise_space_id'], unique=False)
    op.create_index('ix_model_default_model_id', 'model_default', ['model_id'], unique=False)

    op.alter_column('provider_config', 'deployment_type', server_default=None)
    op.alter_column('provider_config', 'sync_status', server_default=None)
    op.alter_column('model_ref', 'model_type', server_default=None)



def downgrade() -> None:
    op.drop_index('ix_model_default_model_id', table_name='model_default')
    op.drop_index('ix_model_default_enterprise_space_id', table_name='model_default')
    op.drop_table('model_default')

    op.drop_constraint('uq_model_ref_provider_model_code', 'model_ref', type_='unique')
    op.drop_constraint('uq_provider_config_space_name_base_url', 'provider_config', type_='unique')

    op.drop_column('model_ref', 'raw_payload')
    op.drop_column('model_ref', 'max_output_tokens')
    op.drop_column('model_ref', 'context_window')
    op.drop_column('model_ref', 'model_type')
    op.drop_column('model_ref', 'model_code')

    op.drop_column('provider_config', 'last_sync_error')
    op.drop_column('provider_config', 'last_sync_at')
    op.drop_column('provider_config', 'sync_status')
    op.drop_column('provider_config', 'supported_types')
    op.drop_column('provider_config', 'deployment_type')
