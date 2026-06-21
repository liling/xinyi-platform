import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.user import AuthProvider, User, UserRole


def _make_session(scalar_result=None):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = scalar_result
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


def _override_factory(mock):
    async def _override():
        yield mock
    return _override


@pytest.fixture
def client():
    return TestClient(app)


def test_register_success(client):
    mock = _make_session(scalar_result=None)
    app.dependency_overrides[get_session] = _override_factory(mock)
    try:
        response = client.post("/register", data={
            "username": "newbie", "password": "MyStrong123!",
            "email": "n@example.com", "display_name": "Newbie",
        }, follow_redirects=False)
        assert response.status_code == 303
    finally:
        app.dependency_overrides.clear()


def test_register_duplicate_username(client):
    existing = User(username="newbie", display_name="x", auth_provider=AuthProvider.LOCAL)
    mock = _make_session(scalar_result=existing)
    app.dependency_overrides[get_session] = _override_factory(mock)
    try:
        response = client.post("/register", data={
            "username": "newbie", "password": "MyStrong123!",
            "email": "n@example.com", "display_name": "Newbie",
        })
        assert response.status_code == 200
        assert "已存在" in response.text or "already" in response.text.lower()
    finally:
        app.dependency_overrides.clear()
