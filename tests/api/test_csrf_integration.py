from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


async def _override_session():
    yield _mock_session()


def test_register_requires_csrf():
    """注册端点无 CSRF token 应返回 403"""
    client = TestClient(app)
    app.dependency_overrides[get_session] = _override_session
    try:
        resp = client.post("/xinyi/register", data={
            "username": "testuser",
            "password": "Test1234",
        })
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_register_with_csrf_succeeds():
    """注册端点带正确 CSRF token 应通过 CSRF 检查"""
    client = TestClient(app)
    app.dependency_overrides[get_session] = _override_session
    try:
        page = client.get("/xinyi/register")
        token = page.cookies.get("xinyi_csrf", "")
        resp = client.post("/xinyi/register", data={
            "username": "testuser2",
            "password": "Test1234",
            "csrf_token": token,
        }, cookies={"xinyi_csrf": token})
        assert resp.status_code != 403
    finally:
        app.dependency_overrides.clear()


def test_json_login_requires_csrf_header():
    """JSON 登录无 CSRF header 应 403"""
    client = TestClient(app)
    app.dependency_overrides[get_session] = _override_session
    try:
        resp = client.post("/xinyi/login", json={
            "username": "admin",
            "password": "test",
        })
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_json_login_with_csrf_header():
    """JSON 登录带正确 X-CSRF-Token header 应通过 CSRF 检查"""
    client = TestClient(app)
    app.dependency_overrides[get_session] = _override_session
    try:
        page = client.get("/xinyi/login")
        token = page.cookies.get("xinyi_csrf", "")
        resp = client.post("/xinyi/login", json={
            "username": "admin",
            "password": "test",
        }, headers={"X-CSRF-Token": token}, cookies={"xinyi_csrf": token})
        assert resp.status_code != 403
    finally:
        app.dependency_overrides.clear()
