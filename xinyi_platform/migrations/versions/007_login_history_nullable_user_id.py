"""allow nullable user_id in login_history for failed login attempts

Revision ID: 007
Revises: 006
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "login_history", "user_id",
        existing_type=sa.UUID(),
        nullable=True,
        schema="xinyi",
    )


def downgrade() -> None:
    op.alter_column(
        "login_history", "user_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema="xinyi",
    )
