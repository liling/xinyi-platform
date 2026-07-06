from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _admin_token():
    s = Settings()
    return create_session_token(
        sub="u-1", username="admin", role="admin",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def _override_session(rows_result=None):
    """Mock session for list_login_history, which now uses result.all()
    (tuples of LoginHistory + User after outerjoin), not scalars().all()."""
    session = MagicMock()
    session.execute = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = rows_result or []
    session.execute.return_value = execute_result

    async def _override():
        yield session
    return _override


def test_list_login_history():
    app.dependency_overrides[get_session] = _override_session(rows_result=[])
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/login-history",
            cookies={"xinyi_session": _admin_token()},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_list_login_history_renders_username_and_display_name():
    """User column shows username + display_name, no longer raw user_id."""
    import uuid
    from datetime import datetime

    from xinyi_platform.models.login_history import LoginHistory
    from xinyi_platform.models.user import AuthProvider, User, UserRole

    user = User(
        id=uuid.uuid4(), username="alice", display_name="爱丽丝",
        email="a@example.com", auth_provider=AuthProvider.LOCAL, role=UserRole.USER,
    )
    history = LoginHistory(
        id=uuid.uuid4(), user_id=user.id,
        ip_address="127.0.0.1", user_agent="test",
        login_time=datetime.now(), success=True,
    )

    app.dependency_overrides[get_session] = _override_session(rows_result=[(history, user)])
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/login-history",
            cookies={"xinyi_session": _admin_token()},
        )
        assert response.status_code == 200
        assert "alice" in response.text
        assert "爱丽丝" in response.text
        assert str(user.id) not in response.text
    finally:
        app.dependency_overrides.clear()


def test_list_login_history_anonymous_login_shows_dash():
    """Failed login without user_id must render username/name as —, not crash."""
    import uuid
    from datetime import datetime

    from xinyi_platform.models.login_history import LoginHistory

    history = LoginHistory(
        id=uuid.uuid4(), user_id=None,
        ip_address="127.0.0.1", user_agent="anon",
        login_time=datetime.now(), success=False,
        failure_reason="用户不存在",
    )

    app.dependency_overrides[get_session] = _override_session(rows_result=[(history, None)])
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/login-history",
            cookies={"xinyi_session": _admin_token()},
        )
        assert response.status_code == 200
        assert "用户不存在" in response.text
    finally:
        app.dependency_overrides.clear()
