"""Add knowledge_base, milvus_connection, neo4j_connection tables

Revision ID: 003_knowledge_base
Revises: 002_model_management
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_knowledge_base'
down_revision: Union[str, None] = '002_model_management'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create knowledge_base table
    op.create_table(
        'knowledge_base',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_space_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='active'),
        sa.Column('vector_db_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('graph_db_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_space_id'], ['enterprise_space.id'], ondelete='CASCADE', name='fk_knowledge_base_enterprise_space_id_enterprise_space'),
        sa.PrimaryKeyConstraint('id', name='pk_knowledge_base'),
    )
    op.create_index('ix_knowledge_base_enterprise_space_id', 'knowledge_base', ['enterprise_space_id'], unique=False)

    # Create milvus_connection table
    op.create_table(
        'milvus_connection',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('knowledge_base_id', sa.Integer(), nullable=False),
        sa.Column('host', sa.String(length=200), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, default=19530),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password', sa.String(length=500), nullable=True),
        sa.Column('collection_name', sa.String(length=200), nullable=True),
        sa.Column('dimension', sa.Integer(), nullable=False, default=1536),
        sa.Column('metric_type', sa.String(length=20), nullable=False, default='COSINE'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_base.id'], ondelete='CASCADE', name='fk_milvus_connection_knowledge_base_id_knowledge_base'),
        sa.PrimaryKeyConstraint('id', name='pk_milvus_connection'),
    )
    op.create_index('ix_milvus_connection_knowledge_base_id', 'milvus_connection', ['knowledge_base_id'], unique=False)

    # Create neo4j_connection table
    op.create_table(
        'neo4j_connection',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('knowledge_base_id', sa.Integer(), nullable=False),
        sa.Column('uri', sa.String(length=500), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=500), nullable=True),
        sa.Column('database', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_base.id'], ondelete='CASCADE', name='fk_neo4j_connection_knowledge_base_id_knowledge_base'),
        sa.PrimaryKeyConstraint('id', name='pk_neo4j_connection'),
    )
    op.create_index('ix_neo4j_connection_knowledge_base_id', 'neo4j_connection', ['knowledge_base_id'], unique=False)


def downgrade() -> None:
    op.drop_table('neo4j_connection')
    op.drop_table('milvus_connection')
    op.drop_table('knowledge_base')
