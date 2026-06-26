import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from xinyi_platform.auth.dependencies import get_current_user, require_admin
from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings


def _make_app():
    app = FastAPI()

    @app.get("/xinyi/me")
    async def me(user=Depends(get_current_user)):
        return user

    @app.get("/xinyi/admin")
    async def admin(user=Depends(require_admin)):
        return user

    return app


def _make_token(role: str = "admin") -> str:
    settings = Settings()
    return create_session_token(
        sub="u-1", username="alice", role=role,
        secret=settings.jwt_secret, ttl_seconds=900,
    )


def test_get_current_user_no_token_returns_401():
    app = _make_app()
    client = TestClient(app)
    response = client.get("/xinyi/me")
    assert response.status_code == 401


def test_get_current_user_invalid_token_returns_401():
    app = _make_app()
    client = TestClient(app)
    response = client.get("/xinyi/me", cookies={"xinyi_session": "garbage"})
    assert response.status_code == 401


def test_get_current_user_valid_token_returns_dict():
    app = _make_app()
    token = _make_token(role="admin")
    client = TestClient(app)
    response = client.get("/xinyi/me", cookies={"xinyi_session": token})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "u-1"
    assert body["username"] == "alice"
    assert body["role"] == "admin"


def test_require_admin_non_admin_returns_403():
    app = _make_app()
    token = _make_token(role="user")
    client = TestClient(app)
    response = client.get("/xinyi/admin", cookies={"xinyi_session": token})
    assert response.status_code == 403


def test_get_current_user_with_bearer_no_response_cookie():
    """Bearer auth path should not crash when Response is not injected."""
    app = _make_app()
    token = _make_token(role="user")
    client = TestClient(app)
    response = client.get("/xinyi/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "u-1"
