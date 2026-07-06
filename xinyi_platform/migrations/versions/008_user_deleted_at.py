"""add users.deleted_at for soft delete

Distinguishes "deleted" (deleted_at IS NOT NULL) from "disabled"
(is_active = False). Previously soft_delete overloaded is_active,
conflating two distinct administrative actions.

Revision ID: 008
Revises: 007
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="xinyi",
    )


def downgrade() -> None:
    op.drop_column("users", "deleted_at", schema="xinyi")
