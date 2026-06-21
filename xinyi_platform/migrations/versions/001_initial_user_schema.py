"""initial user schema

Revision ID: 001
Revises:
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS xinyi")
    op.execute("CREATE TYPE xinyi.auth_provider AS ENUM ('local', 'cas')")
    op.execute("CREATE TYPE xinyi.user_role AS ENUM ('admin', 'user')")
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("auth_provider",
                  sa.Enum("local", "cas", name="auth_provider", schema="xinyi"),
                  nullable=False),
        sa.Column("role",
                  sa.Enum("admin", "user", name="user_role", schema="xinyi"),
                  nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="xinyi",
    )


def downgrade() -> None:
    op.drop_table("users", schema="xinyi")
    op.execute("DROP TYPE IF EXISTS xinyi.user_role")
    op.execute("DROP TYPE IF EXISTS xinyi.auth_provider")
    op.execute("DROP SCHEMA IF EXISTS xinyi CASCADE")
