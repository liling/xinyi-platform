"""add logout_url to business_clients

Revision ID: 004
Revises: 003
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_clients",
        sa.Column("logout_url", sa.String(512), nullable=True),
        schema="xinyi",
    )


def downgrade() -> None:
    op.drop_column("business_clients", "logout_url", schema="xinyi")
