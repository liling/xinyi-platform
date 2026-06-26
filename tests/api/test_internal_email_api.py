from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.auth.internal_auth import verify_internal_client
from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _setup_overrides():
    async def _fake_client():
        return MagicMock(client_id="test")

    async def _fake_session():
        session = MagicMock()
        yield session

    app.dependency_overrides[verify_internal_client] = _fake_client
    app.dependency_overrides[get_session] = _fake_session

    def teardown():
        app.dependency_overrides.clear()
    return teardown


def test_send_email_accepted():
    teardown = _setup_overrides()
    try:
        with patch(
            "xinyi_platform.api.internal.EmailService.send_safe",
        ) as mock_send:
            client = TestClient(app)
            response = client.post(
                "/xinyi/internal/notifications/email",
                headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
                json={
                    "to": ["user@example.com"], "subject": "Hi", "body": "Hello",
                },
            )
        assert response.status_code == 202
        mock_send.assert_called_once()
    finally:
        teardown()
