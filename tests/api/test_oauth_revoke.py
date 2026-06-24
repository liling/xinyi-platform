from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _override_session():
    from unittest.mock import MagicMock
    session = MagicMock()
    session.commit = AsyncMock()
    async def _override():
        yield session
    return _override


def test_revoke_clears_refresh_token():
    with patch(
        "xinyi_platform.api.oauth.OAuthService.revoke_refresh_token",
        new_callable=AsyncMock,
    ) as mock_revoke:
        app.dependency_overrides[get_session] = _override_session()
        try:
            client = TestClient(app)
            response = client.post("/xinyi/oauth/revoke", json={"token": "raw-refresh-token"})
            assert response.status_code == 200
            mock_revoke.assert_called_once()
        finally:
            app.dependency_overrides.clear()


def test_revoke_missing_token_returns_400():
    app.dependency_overrides[get_session] = _override_session()
    try:
        client = TestClient(app)
        response = client.post("/xinyi/oauth/revoke", json={})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
