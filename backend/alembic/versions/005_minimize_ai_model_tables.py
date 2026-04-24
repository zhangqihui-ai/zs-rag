"""Rename model tables and minimize columns

Revision ID: 005_minimize_ai_model_tables
Revises: 004_ai_model_management_page
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_minimize_ai_model_tables"
down_revision: Union[str, None] = "004_ai_model_management_page"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("provider_config", "ai_model_provider")
    op.rename_table("model_ref", "ai_model")
    op.rename_table("model_default", "ai_model_default")

    op.execute("ALTER INDEX ix_provider_config_enterprise_space_id RENAME TO ix_ai_model_provider_enterprise_space_id")
    op.execute("ALTER INDEX ix_model_ref_enterprise_space_id RENAME TO ix_ai_model_enterprise_space_id")
    op.execute("ALTER INDEX ix_model_ref_provider_id RENAME TO ix_ai_model_provider_id")
    op.execute("ALTER INDEX ix_model_default_enterprise_space_id RENAME TO ix_ai_model_default_enterprise_space_id")
    op.execute("ALTER INDEX ix_model_default_model_id RENAME TO ix_ai_model_default_model_id")

    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT pk_provider_config TO pk_ai_model_provider")
    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT uq_provider_config_space_name_base_url TO uq_ai_model_provider_space_name_base_url")
    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT fk_provider_config_enterprise_space_id_enterprise_space TO fk_ai_model_provider_enterprise_space_id_enterprise_space")

    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT pk_model_ref TO pk_ai_model")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT uq_model_ref_provider_model_code TO uq_ai_model_provider_model_code")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT fk_model_ref_enterprise_space_id_enterprise_space TO fk_ai_model_enterprise_space_id_enterprise_space")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT fk_model_ref_provider_id_provider_config TO fk_ai_model_provider_id_ai_model_provider")

    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT pk_model_default TO pk_ai_model_default")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT uq_model_default_space_model_type TO uq_ai_model_default_space_model_type")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT fk_model_default_enterprise_space_id_enterprise_space TO fk_ai_model_default_enterprise_space_id_enterprise_space")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT fk_model_default_model_id_model_ref TO fk_ai_model_default_model_id_ai_model")

    op.alter_column("ai_model_provider", "name", new_column_name="provider_name")
    op.alter_column("ai_model_provider", "provider_type", new_column_name="provider_code")
    op.alter_column("ai_model_provider", "config", new_column_name="auth_config")
    op.alter_column("ai_model_provider", "description", new_column_name="remark")
    op.add_column("ai_model_provider", sa.Column("auth_type", sa.String(length=30), nullable=True))

    op.execute(
        """
        UPDATE ai_model_provider
        SET auth_type = COALESCE(auth_config ->> 'auth_type', 'bearer')
        """
    )
    op.execute(
        """
        UPDATE ai_model_provider
        SET auth_config = COALESCE(auth_config -> 'auth_config', '{}'::json)
        """
    )
    op.execute(
        """
        UPDATE ai_model_provider
        SET auth_config = '{}'::json
        WHERE auth_config IS NULL
        """
    )
    op.alter_column("ai_model_provider", "auth_type", existing_type=sa.String(length=30), nullable=False)
    op.alter_column("ai_model_provider", "auth_config", existing_type=sa.JSON(), nullable=False)

    op.drop_column("ai_model_provider", "api_key")
    op.drop_column("ai_model_provider", "is_active")
    op.drop_column("ai_model_provider", "timeout_seconds")
    op.drop_column("ai_model_provider", "max_retries")
    op.drop_column("ai_model_provider", "supported_types")

    op.alter_column("ai_model", "is_active", new_column_name="is_enabled")
    op.drop_column("ai_model", "display_name")
    op.drop_column("ai_model", "default_params")
    op.drop_column("ai_model", "description")


def downgrade() -> None:
    op.add_column("ai_model", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("ai_model", sa.Column("default_params", sa.JSON(), nullable=True))
    op.add_column("ai_model", sa.Column("display_name", sa.String(length=200), nullable=True))
    op.alter_column("ai_model", "is_enabled", new_column_name="is_active")

    op.add_column("ai_model_provider", sa.Column("supported_types", sa.JSON(), nullable=True))
    op.add_column("ai_model_provider", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("ai_model_provider", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("ai_model_provider", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ai_model_provider", sa.Column("api_key", sa.String(length=500), nullable=False, server_default=""))

    op.execute(
        """
        UPDATE ai_model_provider
        SET api_key = COALESCE(auth_config ->> 'api_key', auth_config ->> 'token', auth_config ->> 'access_token', '')
        """
    )
    op.execute(
        """
        UPDATE ai_model_provider
        SET supported_types = '[]'::json
        WHERE supported_types IS NULL
        """
    )
    op.execute(
        """
        UPDATE ai_model_provider
        SET auth_config = json_build_object(
            'auth_type', COALESCE(auth_type, 'bearer'),
            'auth_config', COALESCE(auth_config, '{}'::json)
        )
        """
    )
    op.alter_column("ai_model_provider", "auth_config", existing_type=sa.JSON(), nullable=True)
    op.drop_column("ai_model_provider", "auth_type")
    op.alter_column("ai_model_provider", "remark", new_column_name="description")
    op.alter_column("ai_model_provider", "auth_config", new_column_name="config")
    op.alter_column("ai_model_provider", "provider_code", new_column_name="provider_type")
    op.alter_column("ai_model_provider", "provider_name", new_column_name="name")

    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT fk_ai_model_default_model_id_ai_model TO fk_model_default_model_id_model_ref")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT fk_ai_model_default_enterprise_space_id_enterprise_space TO fk_model_default_enterprise_space_id_enterprise_space")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT uq_ai_model_default_space_model_type TO uq_model_default_space_model_type")
    op.execute("ALTER TABLE ai_model_default RENAME CONSTRAINT pk_ai_model_default TO pk_model_default")

    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT fk_ai_model_provider_id_ai_model_provider TO fk_model_ref_provider_id_provider_config")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT fk_ai_model_enterprise_space_id_enterprise_space TO fk_model_ref_enterprise_space_id_enterprise_space")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT uq_ai_model_provider_model_code TO uq_model_ref_provider_model_code")
    op.execute("ALTER TABLE ai_model RENAME CONSTRAINT pk_ai_model TO pk_model_ref")

    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT fk_ai_model_provider_enterprise_space_id_enterprise_space TO fk_provider_config_enterprise_space_id_enterprise_space")
    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT uq_ai_model_provider_space_name_base_url TO uq_provider_config_space_name_base_url")
    op.execute("ALTER TABLE ai_model_provider RENAME CONSTRAINT pk_ai_model_provider TO pk_provider_config")

    op.execute("ALTER INDEX ix_ai_model_default_model_id RENAME TO ix_model_default_model_id")
    op.execute("ALTER INDEX ix_ai_model_default_enterprise_space_id RENAME TO ix_model_default_enterprise_space_id")
    op.execute("ALTER INDEX ix_ai_model_provider_id RENAME TO ix_model_ref_provider_id")
    op.execute("ALTER INDEX ix_ai_model_enterprise_space_id RENAME TO ix_model_ref_enterprise_space_id")
    op.execute("ALTER INDEX ix_ai_model_provider_enterprise_space_id RENAME TO ix_provider_config_enterprise_space_id")

    op.rename_table("ai_model_default", "model_default")
    op.rename_table("ai_model", "model_ref")
    op.rename_table("ai_model_provider", "provider_config")

    op.alter_column("provider_config", "timeout_seconds", server_default=None)
    op.alter_column("provider_config", "max_retries", server_default=None)
    op.alter_column("provider_config", "is_active", server_default=None)
    op.alter_column("provider_config", "api_key", server_default=None)
