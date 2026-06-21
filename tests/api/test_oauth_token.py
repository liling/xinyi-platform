import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.services.oauth_service import TokenPair


def _override_session():
    from unittest.mock import MagicMock
    session = MagicMock()
    session.commit = AsyncMock()
    async def _override():
        yield session
    return _override


def test_token_grant_authorization_code_success():
    user_info = {"id": str(uuid.uuid4()), "username": "alice"}
    fake_pair = TokenPair(
        access_token="access-jwt", refresh_token="refresh-raw",
        expires_in=900, user_info=user_info,
    )
    with patch(
        "xinyi_platform.api.oauth.OAuthService.exchange_code",
        new_callable=AsyncMock, return_value=fake_pair,
    ):
        app.dependency_overrides[get_session] = _override_session()
        try:
            client = TestClient(app)
            response = client.post("/oauth/token", json={
                "grant_type": "authorization_code",
                "code": "x", "client_id": "hm-prod",
                "client_secret": "secret", "redirect_uri": "http://hm/cb",
            })
            assert response.status_code == 200
            body = response.json()
            assert body["access_token"] == "access-jwt"
            assert body["refresh_token"] == "refresh-raw"
            assert body["token_type"] == "Bearer"
            assert body["expires_in"] == 900
        finally:
            app.dependency_overrides.clear()


def test_token_grant_invalid_returns_401():
    with patch(
        "xinyi_platform.api.oauth.OAuthService.exchange_code",
        new_callable=AsyncMock, return_value=None,
    ):
        app.dependency_overrides[get_session] = _override_session()
        try:
            client = TestClient(app)
            response = client.post("/oauth/token", json={
                "grant_type": "authorization_code",
                "code": "bad", "client_id": "x", "client_secret": "y",
                "redirect_uri": "z",
            })
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


def test_token_unsupported_grant_type_returns_400():
    app.dependency_overrides[get_session] = _override_session()
    try:
        client = TestClient(app)
        response = client.post("/oauth/token", json={"grant_type": "client_credentials"})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
