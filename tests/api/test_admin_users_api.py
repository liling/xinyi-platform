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
                data={
                    "username": "new", "password": "MyStrong123!",
                    "display_name": "N", "email": "n@example.com",
                    "role": "user",
                },
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            assert response.headers["location"] == "/xinyi/admin/users"
        finally:
            app.dependency_overrides.clear()


def test_create_user_via_form_submission():
    """HTML form submits form-encoded body; endpoint must accept it (not JSON only)."""
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    fake = User(id=uuid.uuid4(), username="newuser", display_name="新用户",
                auth_provider=AuthProvider.LOCAL, role=UserRole.USER)
    with patch(
        "xinyi_platform.api.admin_users.UserService.create_user",
        new_callable=AsyncMock, return_value=fake,
    ) as create_mock:
        app.dependency_overrides[get_session] = _override_session()
        app.dependency_overrides[verify_csrf_token] = _noop_csrf
        try:
            client = TestClient(app)
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                data={
                    "username": "newuser",
                    "password": "MyStrong123!",
                    "display_name": "新用户",
                    "email": "n@example.com",
                    "role": "user",
                },
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text
            assert response.headers["location"] == "/xinyi/admin/users"
            create_mock.assert_awaited_once()
            kwargs = create_mock.await_args.kwargs
            assert kwargs["username"] == "newuser"
            assert kwargs["password"] == "MyStrong123!"
            assert kwargs["email"] == "n@example.com"
            assert kwargs["display_name"] == "新用户"
            assert kwargs["role"] == UserRole.USER
        finally:
            app.dependency_overrides.clear()


def test_create_user_weak_password_returns_400_not_500():
    """Weak password must surface as 400, not crash the app as 500."""
    from xinyi_platform.auth.password import PasswordStrengthError
    app.dependency_overrides[get_session] = _override_session()
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        with patch(
            "xinyi_platform.api.admin_users.UserService.create_user",
            new_callable=AsyncMock,
            side_effect=PasswordStrengthError("Password must contain at least one uppercase letter"),
        ):
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                data={
                    "username": "weakpw",
                    "password": "weakpassword",
                    "display_name": "弱密码用户",
                    "role": "user",
                },
            )
        assert response.status_code == 400, response.text
        assert "uppercase" in response.text
    finally:
        app.dependency_overrides.clear()


def test_create_user_weak_password_returns_html_error_page():
    """Form submission on failure must re-render the form HTML with error message,
    not raw JSON (browsers can't display JSON error details gracefully)."""
    from xinyi_platform.auth.password import PasswordStrengthError
    app.dependency_overrides[get_session] = _override_session()
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        with patch(
            "xinyi_platform.api.admin_users.UserService.create_user",
            new_callable=AsyncMock,
            side_effect=PasswordStrengthError("Password must contain at least one uppercase letter"),
        ):
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                data={
                    "username": "weakpw",
                    "password": "weakpassword",
                    "display_name": "弱密码用户",
                    "role": "user",
                },
            )
        assert response.status_code == 400, response.text
        assert response.headers["content-type"].startswith("text/html"), response.headers
        assert "Password must contain at least one uppercase letter" in response.text
        assert "<form" in response.text
    finally:
        app.dependency_overrides.clear()


def test_create_user_invalid_email_returns_400_with_chinese_error():
    """Regression: email format must be validated; 'not_an_email' was accepted silently."""
    app.dependency_overrides[get_session] = _override_session()
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        with patch(
            "xinyi_platform.api.admin_users.UserService.create_user",
            new_callable=AsyncMock,
        ) as create_mock:
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                data={
                    "username": "bademail",
                    "password": "MyStrong123!",
                    "display_name": "Bad Email",
                    "email": "not_an_email",
                    "role": "user",
                },
            )
        assert response.status_code == 400, response.text
        assert "邮箱格式不正确" in response.text
        create_mock.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


def test_update_user_persists_email_and_is_active():
    """Regression: update_user ignored email field, and is_active checkbox default
    was 'true' so unchecking had no effect."""
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    user = User(
        id=uuid.uuid4(), username="victim", display_name="V",
        email="old@example.com", auth_provider=AuthProvider.LOCAL,
        role=UserRole.USER, is_active=True,
    )
    session_mock = MagicMock()
    session_mock.get = AsyncMock(return_value=user)
    session_mock.commit = AsyncMock()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        response = client.post(
            f"/xinyi/admin/users/{user.id}",
            cookies={"xinyi_session": _admin_token()},
            data={
                "display_name": "V2",
                "email": "new@example.com",
                "role": "admin",
                # is_active checkbox unchecked: not sent
            },
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        assert user.email == "new@example.com"
        assert user.role == UserRole.ADMIN
        assert user.is_active is False
        assert user.display_name == "V2"
    finally:
        app.dependency_overrides.clear()


def test_update_user_with_invalid_email_returns_400():
    """Regression: email validation must apply on update too."""
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    user = User(
        id=uuid.uuid4(), username="victim", display_name="V",
        email="old@example.com", auth_provider=AuthProvider.LOCAL,
        role=UserRole.USER, is_active=True,
    )
    session_mock = MagicMock()
    session_mock.get = AsyncMock(return_value=user)
    session_mock.commit = AsyncMock()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        response = client.post(
            f"/xinyi/admin/users/{user.id}",
            cookies={"xinyi_session": _admin_token()},
            data={"display_name": "V", "email": "still_not_email", "role": "user"},
        )
        assert response.status_code == 400, response.text
        assert "邮箱格式不正确" in response.text
        assert "<form" in response.text
    finally:
        app.dependency_overrides.clear()


def test_create_user_redirects_to_list_after_success():
    """Regression: create_user returned raw JSON; must redirect (PRG pattern)."""
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
                data={
                    "username": "new", "password": "MyStrong123!",
                    "display_name": "N", "role": "user",
                },
                follow_redirects=False,
            )
            assert response.status_code == 303
            assert response.headers["location"] == "/xinyi/admin/users"
        finally:
            app.dependency_overrides.clear()


def test_create_user_duplicate_username_shows_chinese_error():
    """Regression: UsernameConflictError message was English while UI is Chinese."""
    from xinyi_platform.services.user_service import UsernameConflictError
    app.dependency_overrides[get_session] = _override_session()
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        with patch(
            "xinyi_platform.api.admin_users.UserService.create_user",
            new_callable=AsyncMock,
            side_effect=UsernameConflictError("用户名 'dup' 已存在"),
        ):
            response = client.post(
                "/xinyi/admin/users",
                cookies={"xinyi_session": _admin_token()},
                data={"username": "dup", "password": "MyStrong123!", "role": "user"},
            )
        assert response.status_code == 400
        assert "用户名" in response.text
        assert "已存在" in response.text
    finally:
        app.dependency_overrides.clear()


def test_delete_user_sets_deleted_at_not_is_active():
    """Regression: soft_delete previously set is_active=False, conflating
    'disabled' with 'deleted'. Now it sets deleted_at and leaves is_active alone."""
    import datetime as dt
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    user = User(
        id=uuid.uuid4(), username="victim", display_name="V",
        auth_provider=AuthProvider.LOCAL, role=UserRole.USER, is_active=True,
    )
    session_mock = MagicMock()
    session_mock.get = AsyncMock(return_value=user)
    session_mock.commit = AsyncMock()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        client = TestClient(app)
        response = client.post(
            f"/xinyi/admin/users/{user.id}/delete",
            cookies={"xinyi_session": _admin_token()},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        assert user.deleted_at is not None
        assert user.is_active is True  # untouched
    finally:
        app.dependency_overrides.clear()


def test_list_users_excludes_deleted_but_shows_disabled():
    """Regression: list must show disabled (is_active=False) users so admin
    can re-enable them, but hide deleted (deleted_at IS NOT NULL) users."""
    from xinyi_platform.models.user import AuthProvider, User, UserRole
    import datetime as dt
    active = User(id=uuid.uuid4(), username="active", display_name="A",
                  auth_provider=AuthProvider.LOCAL, role=UserRole.USER, is_active=True)
    disabled = User(id=uuid.uuid4(), username="disabled", display_name="D",
                   auth_provider=AuthProvider.LOCAL, role=UserRole.USER, is_active=False)
    deleted = User(id=uuid.uuid4(), username="deleted", display_name="X",
                   auth_provider=AuthProvider.LOCAL, role=UserRole.USER,
                   deleted_at=dt.datetime.now(dt.timezone.utc))

    captured = {}

    async def _fake_execute(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        scalars_mock = MagicMock()
        # Return all three to verify the filter is in SQL, not Python
        scalars_mock.all.return_value = [active, disabled, deleted]
        result.scalars.return_value = scalars_mock
        return result

    session_mock = MagicMock()
    session_mock.execute = _fake_execute

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override
    try:
        client = TestClient(app)
        response = client.get(
            "/xinyi/admin/users",
            cookies={"xinyi_session": _admin_token()},
        )
        assert response.status_code == 200, response.text
        compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at" in compiled
    finally:
        app.dependency_overrides.clear()
