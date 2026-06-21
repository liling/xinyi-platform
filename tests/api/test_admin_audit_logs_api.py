from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_access_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _admin_token():
    s = Settings()
    return create_access_token(
        sub="u-1", username="admin", role="admin",
        client_id="xinyi-platform-self",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _override_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.commit = AsyncMock()

    async def _override():
        yield session
    return _override


def test_filter_by_client_id():
    with patch(
        "xinyi_platform.api.admin_audit.AuditService.query",
        new_callable=AsyncMock, return_value=[],
    ):
        app.dependency_overrides[get_session] = _override_session()
        try:
            client = TestClient(app)
            response = client.get(
                "/admin/audit-logs?client_id=hm-prod",
                cookies={"xinyi_session": _admin_token()},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
