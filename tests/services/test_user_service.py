import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from xinyi_platform.models.user import AuthProvider, User, UserRole
from xinyi_platform.services.user_service import (
    UserService,
    UsernameConflictError,
)


def _make_session():
    """session is a MagicMock (sync); session.execute is AsyncMock returning a sync MagicMock."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def mock_session():
    return _make_session()


async def test_create_user_success(mock_session):
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    user = await UserService.create_user(
        mock_session,
        username="alice",
        password="MyStrong123!",
        email="alice@example.com",
        display_name="Alice",
        provider=AuthProvider.LOCAL,
    )
    assert user.username == "alice"
    assert user.role == UserRole.USER
    assert user.auth_provider == AuthProvider.LOCAL
    assert user.password_hash != "MyStrong123!"
    mock_session.add.assert_called_once()


async def test_create_user_duplicate_username_fails(mock_session):
    existing = User(username="alice", display_name="x", auth_provider=AuthProvider.LOCAL)
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing

    with pytest.raises(UsernameConflictError):
        await UserService.create_user(
            mock_session,
            username="alice",
            password="MyStrong123!",
            email="a@b.com",
            display_name="Alice",
            provider=AuthProvider.LOCAL,
        )


async def test_authenticate_local_success(mock_session):
    from xinyi_platform.auth.password import hash_password
    user = User(
        username="alice",
        display_name="Alice",
        auth_provider=AuthProvider.LOCAL,
        password_hash=hash_password("MyStrong123!"),
        is_active=True,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = user

    result = await UserService.authenticate_local(mock_session, "alice", "MyStrong123!")
    assert result is user


async def test_authenticate_local_wrong_password(mock_session):
    from xinyi_platform.auth.password import hash_password
    user = User(
        username="alice", display_name="x", auth_provider=AuthProvider.LOCAL,
        password_hash=hash_password("MyStrong123!"), is_active=True,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = user

    result = await UserService.authenticate_local(mock_session, "alice", "wrong")
    assert result is None


async def test_authenticate_local_inactive(mock_session):
    from xinyi_platform.auth.password import hash_password
    user = User(
        username="alice", display_name="x", auth_provider=AuthProvider.LOCAL,
        password_hash=hash_password("MyStrong123!"), is_active=False,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = user

    result = await UserService.authenticate_local(mock_session, "alice", "MyStrong123!")
    assert result is None


async def test_batch_get_returns_dict(mock_session):
    u1 = User(id=uuid.uuid4(), username="a", display_name="A",
              auth_provider=AuthProvider.LOCAL, role=UserRole.USER)
    u2 = User(id=uuid.uuid4(), username="b", display_name="B",
              auth_provider=AuthProvider.LOCAL, role=UserRole.ADMIN)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [u1, u2]
    mock_session.execute.return_value.scalars.return_value = scalars_mock

    result = await UserService.batch_get(mock_session, [u1.id, u2.id])
    assert result[u1.id]["username"] == "a"
    assert result[u2.id]["username"] == "b"
    assert result[u1.id]["role"] == "user"
    assert result[u2.id]["role"] == "admin"


async def test_get_by_id_excludes_soft_deleted():
    """Regression: get_by_id must not return soft-deleted users.
    Internal API relies on this to return 404 for deleted users."""
    captured = {}
    user = User(id=uuid.uuid4(), username="alive", display_name="A",
                auth_provider=AuthProvider.LOCAL)

    async def _capture(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        return result

    session = MagicMock()
    session.execute = _capture

    out = await UserService.get_by_id(session, user.id)
    assert out is user
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in compiled


async def test_get_by_username_excludes_soft_deleted():
    """Regression: get_by_username must not return soft-deleted users."""
    captured = {}
    user = User(username="alive", display_name="A", auth_provider=AuthProvider.LOCAL)

    async def _capture(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        return result

    session = MagicMock()
    session.execute = _capture

    out = await UserService.get_by_username(session, "alive")
    assert out is user
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in compiled


async def test_batch_get_excludes_soft_deleted():
    """Regression: batch_get must filter deleted_at so internal callers
    don't receive deleted users in batch responses."""
    captured = {}

    async def _capture(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result.scalars.return_value = scalars_mock
        return result

    session = MagicMock()
    session.execute = _capture

    await UserService.batch_get(session, [uuid.uuid4()])
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in compiled


async def test_search_excludes_soft_deleted():
    """Regression: search must filter deleted_at so deleted users don't
    appear in typeahead/search results."""
    captured = {}

    async def _capture(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result.scalars.return_value = scalars_mock
        return result

    session = MagicMock()
    session.execute = _capture

    await UserService.search(session, "alice")
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in compiled
