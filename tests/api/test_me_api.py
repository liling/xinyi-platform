import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.user import AuthProvider, User, UserRole


def _token(role: str = "admin"):
    s = Settings()
    return create_session_token(
        sub="00000000-0000-0000-0000-000000000001", username="alice", role=role,
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _override_session_with_user(db_user: User):
    """Override get_session to return a specific User via session.get()."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=db_user)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _override():
        yield session
    return _override


def test_me_without_token_returns_401():
    client = TestClient(app)
    response = client.get("/xinyi/me")
    assert response.status_code == 401


def test_me_with_valid_token_returns_user():
    client = TestClient(app)
    response = client.get("/xinyi/me", cookies={"xinyi_session": _token()})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"


def test_account_page_shows_all_six_profile_fields():
    """GET /account renders username, role, display_name, email, auth_provider, is_active."""
    # Build a fake DB user matching the token's sub="u-1"
    fake_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        username="alice",
        display_name="Alice Smith",
        email="alice@example.com",
        auth_provider=AuthProvider.LOCAL,
        role=UserRole.ADMIN,
        is_active=True,
    )
    app.dependency_overrides[get_session] = _override_session_with_user(fake_user)
    try:
        client = TestClient(app)
        resp = client.get("/xinyi/account", cookies={"xinyi_session": _token()})
        assert resp.status_code == 200
        html = resp.text
        for label in ["用户名", "显示名称", "邮箱", "角色", "认证方式", "账号状态"]:
            assert label in html, f"missing field label: {label}"
    finally:
        app.dependency_overrides.clear()


def test_account_page_unauthenticated_redirects_to_login():
    """Browser navigation (Accept: text/html) to a protected page without a
    session should redirect to /login, not return 401 JSON."""
    client = TestClient(app)
    resp = client.get(
        "/xinyi/account", headers={"Accept": "text/html"}, follow_redirects=False
    )
    assert resp.status_code in (301, 302, 303, 307)
    location = resp.headers["location"]
    assert location.startswith("/xinyi/login")
    assert "return_to=" in location


def test_api_unauthenticated_keeps_401_json():
    """Non-browser requests (no Accept: text/html) must keep returning 401 JSON
    so the auth handler does not redirect API clients."""
    client = TestClient(app)
    resp = client.get("/xinyi/me", follow_redirects=False)
    assert resp.status_code == 401
    assert "detail" in resp.json()
