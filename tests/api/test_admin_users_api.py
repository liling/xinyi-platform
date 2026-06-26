import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.middleware.csrf import verify_csrf_token


async def _noop_csrf():
    pass


def _admin_token():
    s = Settings()
    return create_session_token(
        sub=str(uuid.uuid4()), username="admin", role="admin",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _user_token():
    s = Settings()
    return create_session_token(
        sub=str(uuid.uuid4()), username="user", role="user",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _override_session(scalar_result=None, scalars_result=None):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = scalar_result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_result or []
    session.execute.return_value.scalars.return_value = scalars_mock
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()

    async def _override():
        yield session
    return _override


def test_list_users_as_non_admin_returns_403():
    app.dependency_overrides[get_session] = _override_session()
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/users",
            cookies={"xinyi_session": _user_token()},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_create_user_as_non_admin_returns_403():
    app.dependency_overrides[get_session] = _override_session()
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        response = client.post(
            "/xinyi/admin/users",
            cookies={"xinyi_session": _user_token()},
            json={"username": "x", "password": "MyStrong123!", "display_name": "X"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_create_user_as_admin():
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    fake = User(id=uuid.uuid4(), username="new", display_name="N",
                auth_provider=AuthProvider.LOCAL, role=UserRole.USER)
    with patch(
        "xinyi_platform.api.admin_users.UserService.create_user",
        new_callable=AsyncMock, return_value=fake,
    ):
        app.dependency_overrides[get_session] = _override_session()
        app.dependency_overrides[verify_csrf_token] = _noop_csrf
        try:
            client = TestClient(app)
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                json={
                    "username": "new", "password": "MyStrong123!",
                    "display_name": "N", "email": "n@example.com",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["username"] == "new"
        finally:
            app.dependency_overrides.clear()
