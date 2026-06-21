import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from xinyi_platform.config import Settings
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.models.oauth_code import OAuthCode
from xinyi_platform.models.refresh_token import RefreshToken
from xinyi_platform.models.user import AuthProvider, User, UserRole
from xinyi_platform.services.oauth_service import OAuthService

TEST_SECRET = "test-secret-with-at-least-32-characters!!"


def _make_settings():
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret=TEST_SECRET,
        encryption_key="00112233445566778899aabbccddeeff",
        admin_password="x",
        access_token_ttl_seconds=900,
        refresh_token_ttl_days=7,
        oauth_code_ttl_seconds=60,
    )


def _make_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def settings():
    return _make_settings()


@pytest.fixture
def mock_session():
    return _make_session()


async def test_generate_code_returns_random_string(mock_session, settings):
    user_id = uuid.uuid4()
    code = await OAuthService.generate_code(
        mock_session,
        client_id="hm-prod",
        user_id=user_id,
        redirect_uri="http://hm:8001/auth/callback",
        scope=None,
        ttl_seconds=settings.oauth_code_ttl_seconds,
    )
    assert isinstance(code, str)
    assert len(code) >= 32


async def test_lookup_code_expired_returns_none(mock_session):
    oauth_code = OAuthCode(
        code="x", client_id="hm", user_id=uuid.uuid4(),
        redirect_uri="x",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        used_at=None,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = oauth_code
    result = await OAuthService._lookup_code(mock_session, "x")
    assert result is None


async def test_lookup_code_already_used_returns_none(mock_session):
    oauth_code = OAuthCode(
        code="x", client_id="hm", user_id=uuid.uuid4(),
        redirect_uri="x",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
        used_at=datetime.now(timezone.utc),
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = oauth_code
    result = await OAuthService._lookup_code(mock_session, "x")
    assert result is None


async def test_issue_token_pair_returns_correct_fields(mock_session, settings):
    user_id = uuid.uuid4()
    user = User(
        id=user_id, username="alice", display_name="Alice",
        email="a@b.com", auth_provider=AuthProvider.LOCAL, role=UserRole.ADMIN,
    )
    pair = await OAuthService._issue_token_pair(
        mock_session, user=user, client_id="hm-prod", settings=settings,
    )
    assert pair.expires_in == 900
    assert pair.user_info["username"] == "alice"
    assert pair.user_info["role"] == "admin"
    assert pair.access_token
    assert pair.refresh_token
    assert len(pair.refresh_token) >= 32


async def test_is_user_revoked_true_when_revocation_exists(mock_session):
    user_id = uuid.uuid4()
    revocation = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = revocation
    assert await OAuthService.is_user_revoked(mock_session, user_id) is True


async def test_is_user_revoked_false_when_no_revocation(mock_session):
    user_id = uuid.uuid4()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    assert await OAuthService.is_user_revoked(mock_session, user_id) is False


async def test_revoke_refresh_token_marks_revoked(mock_session):
    rt = RefreshToken(
        id=uuid.uuid4(), user_id=uuid.uuid4(), client_id="hm",
        token_hash="abc",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = rt
    await OAuthService.revoke_refresh_token(mock_session, "raw-token")
    assert rt.revoked_at is not None


async def test_revoke_refresh_token_idempotent(mock_session):
    rt = RefreshToken(
        id=uuid.uuid4(), user_id=uuid.uuid4(), client_id="hm",
        token_hash="abc",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        revoked_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    original_revoked = rt.revoked_at
    mock_session.execute.return_value.scalar_one_or_none.return_value = rt
    await OAuthService.revoke_refresh_token(mock_session, "raw-token")
    assert rt.revoked_at == original_revoked
