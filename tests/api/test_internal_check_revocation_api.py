import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.auth.internal_auth import verify_internal_client
from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _setup_overrides():
    async def _fake_client():
        return MagicMock(client_id="test")

    async def _fake_session():
        session = MagicMock()
        session.execute = AsyncMock()
        session.execute.return_value = MagicMock()
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[verify_internal_client] = _fake_client
    app.dependency_overrides[get_session] = _fake_session

    def teardown():
        app.dependency_overrides.clear()
    return teardown


def test_check_revocation_returns_false():
    teardown = _setup_overrides()
    try:
        with patch(
            "xinyi_platform.api.internal.OAuthService.is_user_revoked",
            new_callable=AsyncMock, return_value=False,
        ):
            client = TestClient(app)
            response = client.post(
                "/internal/auth/check-revocation",
                headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
                json={"user_id": str(uuid.uuid4())},
            )
        assert response.status_code == 200
        assert response.json() == {"revoked": False}
    finally:
        teardown()
