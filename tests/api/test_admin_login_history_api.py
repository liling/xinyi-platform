from unittest.mock import AsyncMock, MagicMock

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


def _override_session(scalars_result=None):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_result or []
    session.execute.return_value.scalars.return_value = scalars_mock

    async def _override():
        yield session
    return _override


def test_list_login_history():
    app.dependency_overrides[get_session] = _override_session(scalars_result=[])
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/login-history",
            cookies={"xinyi_session": _admin_token()},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
