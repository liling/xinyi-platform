from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.business_client import BusinessClient, ClientStatus


def _self_token():
    s = Settings()
    return create_session_token(
        sub="00000000-0000-0000-0000-000000000001",
        username="alice", role="admin",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _fake_active_client():
    return BusinessClient(
        client_id="hm-prod", name="HM", client_secret_hash="x",
        redirect_uris=["http://hm:8001/auth/callback"],
        status=ClientStatus.ACTIVE,
    )


def _override_session(scalar_result):
    from unittest.mock import MagicMock
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = scalar_result
    session.commit = AsyncMock()

    async def _override():
        yield session
    return _override


def test_authorize_unauthenticated_redirects_to_login():
    app.dependency_overrides[get_session] = _override_session(_fake_active_client())
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/oauth/authorize",
            params={
                "response_type": "code", "client_id": "hm-prod",
                "redirect_uri": "http://hm:8001/auth/callback", "state": "xyz",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/xinyi/login" in response.headers["location"]
    finally:
        app.dependency_overrides.clear()


def test_authorize_invalid_client_id_returns_400():
    app.dependency_overrides[get_session] = _override_session(None)
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/oauth/authorize",
            params={
                "response_type": "code", "client_id": "nonexistent",
                "redirect_uri": "http://hm:8001/auth/callback", "state": "xyz",
            },
            cookies={"xinyi_session": _self_token()},
            follow_redirects=False,
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_authorize_redirect_uri_not_in_whitelist_returns_400():
    app.dependency_overrides[get_session] = _override_session(_fake_active_client())
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/oauth/authorize",
            params={
                "response_type": "code", "client_id": "hm-prod",
                "redirect_uri": "http://evil.com/cb", "state": "xyz",
            },
            cookies={"xinyi_session": _self_token()},
            follow_redirects=False,
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_authorize_authenticated_redirects_with_code():
    with patch(
        "xinyi_platform.api.oauth.OAuthService.generate_code",
        new_callable=AsyncMock, return_value="fake-code",
    ):
        app.dependency_overrides[get_session] = _override_session(_fake_active_client())
        try:
            client = TestClient(app)
            response = client.get(
                "/xinyi/oauth/authorize",
                params={
                    "response_type": "code", "client_id": "hm-prod",
                    "redirect_uri": "http://hm:8001/auth/callback", "state": "xyz",
                },
                cookies={"xinyi_session": _self_token()},
                follow_redirects=False,
            )
            assert response.status_code == 303
            assert "code=fake-code" in response.headers["location"]
            assert "state=xyz" in response.headers["location"]
        finally:
            app.dependency_overrides.clear()
