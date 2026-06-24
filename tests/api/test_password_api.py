import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.email_verification import EmailVerification
from xinyi_platform.models.user import AuthProvider, User


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


def test_forgot_password_sends_email(client):
    user = User(
        id=uuid.uuid4(), username="alice", display_name="Alice",
        email="alice@example.com", auth_provider=AuthProvider.LOCAL,
    )
    mock = _make_session(scalar_result=user)
    app.dependency_overrides[get_session] = _override_factory(mock)
    try:
        with patch("xinyi_platform.api.password.EmailService.send_safe") as mock_send:
            response = client.post("/xinyi/password/forgot", data={"email": "alice@example.com"})
        assert response.status_code == 200
        mock_send.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_reset_password_with_valid_token(client):
    user = User(
        id=uuid.uuid4(), username="alice", display_name="Alice",
        email="alice@example.com", auth_provider=AuthProvider.LOCAL,
        password_hash="old",
    )
    verification = EmailVerification(
        id=uuid.uuid4(), email="alice@example.com", code="123456",
        purpose="reset_password",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        verified=False, attempts=0,
    )

    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()

    # Two sequential execute calls: first returns verification, second returns user
    first_result = MagicMock()
    first_result.scalar_one_or_none.return_value = verification
    second_result = MagicMock()
    second_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [first_result, second_result]
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=user)

    app.dependency_overrides[get_session] = _override_factory(session)
    try:
        response = client.post("/xinyi/password/reset", data={
            "email": "alice@example.com", "code": "123456",
            "new_password": "NewStrong123!",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert user.password_hash != "old"
        assert verification.verified is True
    finally:
        app.dependency_overrides.clear()
