import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.user import AuthProvider, User, UserRole


def _make_session(user_for_query=None):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = user_for_query
    session.commit = AsyncMock()
    return session


def _override_session_factory(mock_session):
    async def _override():
        yield mock_session
    return _override


@pytest.fixture
def client():
    return TestClient(app)


def test_login_form_success_sets_cookie(client):
    user = User(
        id=uuid.uuid4(), username="alice", display_name="Alice",
        auth_provider=AuthProvider.LOCAL, role=UserRole.ADMIN, is_active=True,
        password_hash="$2b$12$abc",
    )
    mock = _make_session(user)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        with patch("xinyi_platform.api.login.verify_password", return_value=True):
            response = client.post(
                "/login/form",
                data={"username": "alice", "password": "MyStrong123!"},
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert "xinyi_session" in response.cookies
    finally:
        app.dependency_overrides.clear()


def test_login_form_wrong_password_returns_login_page(client):
    user = User(
        id=uuid.uuid4(), username="alice", display_name="Alice",
        auth_provider=AuthProvider.LOCAL, role=UserRole.USER, is_active=True,
        password_hash="$2b$12$abc",
    )
    mock = _make_session(user)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        with patch("xinyi_platform.api.login.verify_password", return_value=False):
            response = client.post(
                "/login/form",
                data={"username": "alice", "password": "wrong"},
            )
        assert response.status_code == 200
        assert "用户名或密码错误" in response.text
    finally:
        app.dependency_overrides.clear()


def test_login_json_api_success(client):
    user = User(
        id=uuid.uuid4(), username="alice", display_name="Alice",
        auth_provider=AuthProvider.LOCAL, role=UserRole.USER, is_active=True,
        password_hash="$2b$12$abc",
    )
    mock = _make_session(user)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        with patch("xinyi_platform.api.login.verify_password", return_value=True):
            response = client.post(
                "/login",
                json={"provider": "local", "username": "alice", "password": "MyStrong123!"},
            )
        assert response.status_code == 200
        body = response.json()
        assert "token" in body
        assert body["user"]["username"] == "alice"
        assert "xinyi_session" in response.cookies
    finally:
        app.dependency_overrides.clear()
