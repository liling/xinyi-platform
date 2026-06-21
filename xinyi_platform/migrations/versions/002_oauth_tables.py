"""oauth tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE xinyi.client_status AS ENUM ('active', 'disabled')")
    op.create_table(
        "business_clients",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_secret_hash", sa.String(255), nullable=False),
        sa.Column("redirect_uris", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("status",
                  sa.Enum("active", "disabled", name="client_status", schema="xinyi"),
                  nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="xinyi",
    )
    op.create_table(
        "oauth_codes",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("scope", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="xinyi",
    )
    op.create_index("ix_oauth_codes_client_id", "oauth_codes", ["client_id"], schema="xinyi")
    op.create_index("ix_oauth_codes_user_id", "oauth_codes", ["user_id"], schema="xinyi")
    op.create_index("ix_oauth_codes_expires_at", "oauth_codes", ["expires_at"], schema="xinyi")
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("xinyi.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="xinyi",
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema="xinyi")
    op.create_index("ix_refresh_tokens_client_id", "refresh_tokens", ["client_id"], schema="xinyi")
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], schema="xinyi")
    op.create_table(
        "token_revocations",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="xinyi",
    )
    op.create_index("ix_token_revocations_user_id", "token_revocations", ["user_id"], schema="xinyi")
    op.create_index("ix_token_revocations_expires_at", "token_revocations", ["expires_at"], schema="xinyi")


def downgrade() -> None:
    op.drop_table("token_revocations", schema="xinyi")
    op.drop_table("refresh_tokens", schema="xinyi")
    op.drop_table("oauth_codes", schema="xinyi")
    op.drop_table("business_clients", schema="xinyi")
    op.execute("DROP TYPE IF EXISTS xinyi.client_status")
