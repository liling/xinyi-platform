import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from xinyi_platform.config import Settings
from xinyi_platform.main import settings
from xinyi_platform.models.user import AuthProvider, User, UserRole
from xinyi_platform.startup import seed_admin_if_absent


def _make_settings(admin_password: str = "AdminPwd123!"):
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret="x" * 40,
        encryption_key="00112233445566778899aabbccddeeff",
        admin_username="admin",
        admin_password=admin_password,
    )


def _make_session(scalar_result=None):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = scalar_result
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


async def test_seed_admin_creates_when_absent():
    session = _make_session(scalar_result=None)
    settings = _make_settings()
    await seed_admin_if_absent(session, settings)
    session.add.assert_called_once()
    added_user = session.add.call_args[0][0]
    assert added_user.username == "admin"
    assert added_user.role == UserRole.ADMIN
    assert added_user.password_hash != "AdminPwd123!"


async def test_seed_admin_skips_when_already_exists():
    existing = User(
        id=uuid.uuid4(), username="root", display_name="root",
        auth_provider=AuthProvider.LOCAL, role=UserRole.ADMIN,
    )
    session = _make_session(scalar_result=existing)
    settings = _make_settings()
    await seed_admin_if_absent(session, settings)
    session.add.assert_not_called()


async def test_seed_admin_skips_when_password_blank():
    session = _make_session(scalar_result=None)
    settings = _make_settings(admin_password="")
    await seed_admin_if_absent(session, settings)
    session.add.assert_not_called()


def test_session_secure_warning_when_disabled(caplog):
    """session_secure=False 时应输出 WARNING 日志"""
    with caplog.at_level(logging.WARNING, logger="xinyi_platform"):
        # 直接调用检查函数
        from xinyi_platform.main import _warn_if_session_insecure
        _warn_if_session_insecure(settings.__class__(session_secure=False))
    assert any("SESSION_SECURE is False" in r.message for r in caplog.records)


def test_session_secure_no_warning_when_enabled(caplog):
    """session_secure=True 时不应输出 WARNING"""
    with caplog.at_level(logging.WARNING, logger="xinyi_platform"):
        from xinyi_platform.main import _warn_if_session_insecure
        _warn_if_session_insecure(settings.__class__(session_secure=True))
    assert not any("SESSION_SECURE" in r.message for r in caplog.records)
