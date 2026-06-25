"""convert redirect_uris and logout_url to relative paths

Revision ID: 006
Revises: 005
Create Date: 2026-06-25

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _strip_base_url(full_url, base_url):
    """Strip base_url prefix from a full URL, returning relative path."""
    if full_url and base_url and full_url.startswith(base_url):
        return full_url[len(base_url):]
    return full_url


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text("SELECT id, base_url, redirect_uris, logout_url FROM xinyi.business_clients")
    ).fetchall()

    for row in rows:
        client_id, base_url, redirect_uris, logout_url = row
        if not base_url:
            continue

        new_redirect_uris = (
            [_strip_base_url(u, base_url) for u in redirect_uris]
            if redirect_uris is not None
            else None
        )
        new_logout_url = _strip_base_url(logout_url, base_url)

        conn.execute(
            sa.text(
                "UPDATE xinyi.business_clients "
                "SET redirect_uris = CAST(:ru AS jsonb), logout_url = :lu "
                "WHERE id = :id"
            ),
            {
                "ru": json.dumps(new_redirect_uris) if new_redirect_uris is not None else None,
                "lu": new_logout_url,
                "id": client_id,
            },
        )


def downgrade() -> None:
    # Cannot reverse — relative paths cannot be expanded back to full URLs
    # without knowing the historical base_url (which may have changed).
    pass
