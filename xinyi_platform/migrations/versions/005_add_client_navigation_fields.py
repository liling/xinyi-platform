"""add client navigation fields

Revision ID: 005
Revises: 004
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_clients", sa.Column("base_url", sa.String(512), nullable=True), schema="xinyi")
    op.add_column("business_clients", sa.Column("home_path", sa.String(255), nullable=True), schema="xinyi")
    op.add_column("business_clients", sa.Column("description", sa.String(255), nullable=True), schema="xinyi")
    op.add_column("business_clients", sa.Column("logo_url", sa.String(512), nullable=True), schema="xinyi")
    op.add_column("business_clients", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True), schema="xinyi")


def downgrade() -> None:
    op.drop_column("business_clients", "last_seen_at", schema="xinyi")
    op.drop_column("business_clients", "logo_url", schema="xinyi")
    op.drop_column("business_clients", "description", schema="xinyi")
    op.drop_column("business_clients", "home_path", schema="xinyi")
    op.drop_column("business_clients", "base_url", schema="xinyi")
