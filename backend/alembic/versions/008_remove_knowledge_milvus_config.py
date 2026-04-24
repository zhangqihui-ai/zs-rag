"""Move Milvus collection settings to knowledge_base and drop knowledge_milvus_config

Revision ID: 008_remove_milvus_cfg
Revises: 007_kb_documents_retrieval
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_remove_milvus_cfg"
down_revision: Union[str, None] = "007_kb_documents_retrieval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_base", sa.Column("milvus_collection_name", sa.String(length=200), nullable=True))
    op.add_column("knowledge_base", sa.Column("milvus_dimension", sa.Integer(), nullable=False, server_default="1536"))
    op.add_column("knowledge_base", sa.Column("milvus_metric_type", sa.String(length=20), nullable=False, server_default="COSINE"))

    op.execute(
        """
        UPDATE knowledge_base kb
        SET
            milvus_collection_name = COALESCE(NULLIF(kmc.collection_name, ''), CONCAT('kb_', kb.enterprise_space_id, '_', kb.id, '_chunks')),
            milvus_dimension = COALESCE(kmc.dimension, 1536),
            milvus_metric_type = COALESCE(NULLIF(kmc.metric_type, ''), 'COSINE')
        FROM knowledge_milvus_config kmc
        WHERE kmc.knowledge_base_id = kb.id
        """
    )

    op.execute(
        """
        UPDATE knowledge_base kb
        SET milvus_collection_name = CONCAT('kb_', kb.enterprise_space_id, '_', kb.id, '_chunks')
        WHERE kb.milvus_collection_name IS NULL OR kb.milvus_collection_name = ''
        """
    )

    op.alter_column("knowledge_base", "milvus_collection_name", existing_type=sa.String(length=200), nullable=False)
    op.alter_column("knowledge_base", "milvus_dimension", existing_type=sa.Integer(), server_default=None)
    op.alter_column("knowledge_base", "milvus_metric_type", existing_type=sa.String(length=20), server_default=None)

    op.drop_table("knowledge_milvus_config")


def downgrade() -> None:
    op.create_table(
        "knowledge_milvus_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("host", sa.String(length=200), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="19530"),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("password", sa.String(length=500), nullable=True),
        sa.Column("collection_name", sa.String(length=200), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("metric_type", sa.String(length=20), nullable=False, server_default="COSINE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"], ondelete="CASCADE", name="fk_knowledge_milvus_config_knowledge_base_id_knowledge_base"),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_milvus_config"),
        sa.UniqueConstraint("knowledge_base_id", name="uq_knowledge_milvus_config_knowledge_base_id"),
    )
    op.create_index("ix_knowledge_milvus_config_knowledge_base_id", "knowledge_milvus_config", ["knowledge_base_id"], unique=False)

    op.execute(
        """
        INSERT INTO knowledge_milvus_config (
            knowledge_base_id,
            host,
            port,
            username,
            password,
            collection_name,
            dimension,
            metric_type,
            is_active,
            config,
            created_at,
            updated_at
        )
        SELECT
            kb.id,
            'milvus',
            19530,
            NULL,
            NULL,
            kb.milvus_collection_name,
            kb.milvus_dimension,
            kb.milvus_metric_type,
            true,
            NULL,
            kb.created_at,
            kb.updated_at
        FROM knowledge_base kb
        """
    )

    op.drop_column("knowledge_base", "milvus_metric_type")
    op.drop_column("knowledge_base", "milvus_dimension")
    op.drop_column("knowledge_base", "milvus_collection_name")
