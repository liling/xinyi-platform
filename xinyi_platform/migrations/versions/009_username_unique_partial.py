"""make username unique only among non-deleted users

The previous UNIQUE(username) constraint blocked recreating a username
that belonged to a soft-deleted user. Replace it with a partial unique
index so deleted usernames can be reused.

Revision ID: 009
Revises: 008
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE xinyi.users DROP CONSTRAINT users_username_key")
    op.execute(
        "CREATE UNIQUE INDEX users_username_active_idx "
        "ON xinyi.users (username) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS xinyi.users_username_active_idx")
    op.execute("ALTER TABLE xinyi.users ADD CONSTRAINT users_username_key UNIQUE (username)")
