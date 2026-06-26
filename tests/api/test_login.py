import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.login_history import LoginHistory
from xinyi_platform.models.user import AuthProvider, User, UserRole


def _make_session(user_for_query=None):
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = user_for_query
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _override_session_factory(mock_session):
    async def _override():
        yield mock_session
    return _override


def _make_user(active=True):
    return User(
        id=uuid.uuid4(), username="admin", display_name="Admin",
        auth_provider=AuthProvider.LOCAL, role=UserRole.ADMIN, is_active=active,
        password_hash="$2b$12$abc",
    )


def _failed_login_history(mock_session):
    return [
        c.args[0] for c in mock_session.add.call_args_list
        if isinstance(c.args[0], LoginHistory) and not c.args[0].success
    ]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    from xinyi_platform.middleware.rate_limit import login_limiter
    login_limiter._buckets.clear()
    yield
    login_limiter._buckets.clear()


def test_login_json_failure_records_history(client):
    user = _make_user()
    mock = _make_session(user)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        with patch("xinyi_platform.api.login.verify_password", return_value=False):
            response = client.post(
                "/xinyi/login",
                json={"provider": "local", "username": "admin", "password": "wrong-password"},
            )
        assert response.status_code == 401
        failed = _failed_login_history(mock)
        assert len(failed) == 1
        assert failed[0].failure_reason is not None
        assert failed[0].user_id == user.id
    finally:
        app.dependency_overrides.clear()


def test_login_form_failure_records_history(client):
    user = _make_user()
    mock = _make_session(user)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        with patch("xinyi_platform.api.login.verify_password", return_value=False):
            response = client.post(
                "/xinyi/login/form",
                data={"username": "admin", "password": "wrong-password", "return_to": "/xinyi/account"},
            )
        assert response.status_code == 200
        failed = _failed_login_history(mock)
        assert len(failed) == 1
        assert failed[0].failure_reason is not None
        assert failed[0].user_id == user.id
    finally:
        app.dependency_overrides.clear()


def test_login_json_failure_user_not_found_records_history(client):
    mock = _make_session(user_for_query=None)
    app.dependency_overrides[get_session] = _override_session_factory(mock)
    try:
        response = client.post(
            "/xinyi/login",
            json={"provider": "local", "username": "ghost", "password": "whatever"},
        )
        assert response.status_code == 401
        failed = _failed_login_history(mock)
        assert len(failed) == 1
        assert failed[0].failure_reason == "user_not_found"
    finally:
        app.dependency_overrides.clear()
