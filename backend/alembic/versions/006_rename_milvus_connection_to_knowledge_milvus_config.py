"""Rename milvus_connection to knowledge_milvus_config

Revision ID: 006_kb_milvus_config_rename
Revises: 005_minimize_ai_model_tables
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "006_kb_milvus_config_rename"
down_revision: Union[str, None] = "005_minimize_ai_model_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_TABLE_NAME = "milvus_connection"
NEW_TABLE_NAME = "knowledge_milvus_config"
OLD_INDEX_NAME = "ix_milvus_connection_knowledge_base_id"
NEW_INDEX_NAME = "ix_knowledge_milvus_config_knowledge_base_id"
OLD_PK_NAME = "pk_milvus_connection"
NEW_PK_NAME = "pk_knowledge_milvus_config"
OLD_FK_NAME = "fk_milvus_connection_knowledge_base_id_knowledge_base"
NEW_FK_NAME = "fk_knowledge_milvus_config_knowledge_base_id_knowledge_base"
UNIQUE_CONSTRAINT_NAME = "uq_knowledge_milvus_config_knowledge_base_id"
OLD_SEQUENCE_NAME = "milvus_connection_id_seq"
NEW_SEQUENCE_NAME = "knowledge_milvus_config_id_seq"


def upgrade() -> None:
    op.rename_table(OLD_TABLE_NAME, NEW_TABLE_NAME)
    op.execute(f"ALTER INDEX IF EXISTS {OLD_INDEX_NAME} RENAME TO {NEW_INDEX_NAME}")
    op.execute(f"ALTER TABLE {NEW_TABLE_NAME} RENAME CONSTRAINT {OLD_PK_NAME} TO {NEW_PK_NAME}")
    op.execute(f"ALTER TABLE {NEW_TABLE_NAME} RENAME CONSTRAINT {OLD_FK_NAME} TO {NEW_FK_NAME}")
    op.execute(f"ALTER SEQUENCE IF EXISTS {OLD_SEQUENCE_NAME} RENAME TO {NEW_SEQUENCE_NAME}")
    op.drop_index(NEW_INDEX_NAME, table_name=NEW_TABLE_NAME)
    op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, NEW_TABLE_NAME, ["knowledge_base_id"])



def downgrade() -> None:
    op.drop_constraint(UNIQUE_CONSTRAINT_NAME, NEW_TABLE_NAME, type_="unique")
    op.create_index(NEW_INDEX_NAME, NEW_TABLE_NAME, ["knowledge_base_id"], unique=False)
    op.execute(f"ALTER SEQUENCE IF EXISTS {NEW_SEQUENCE_NAME} RENAME TO {OLD_SEQUENCE_NAME}")
    op.execute(f"ALTER TABLE {NEW_TABLE_NAME} RENAME CONSTRAINT {NEW_PK_NAME} TO {OLD_PK_NAME}")
    op.execute(f"ALTER TABLE {NEW_TABLE_NAME} RENAME CONSTRAINT {NEW_FK_NAME} TO {OLD_FK_NAME}")
    op.rename_table(NEW_TABLE_NAME, OLD_TABLE_NAME)
    op.execute(f"ALTER INDEX IF EXISTS {NEW_INDEX_NAME} RENAME TO {OLD_INDEX_NAME}")
