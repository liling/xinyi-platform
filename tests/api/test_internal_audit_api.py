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


def test_push_event_accepted():
    teardown = _setup_overrides()
    try:
        with patch(
            "xinyi_platform.api.internal.AuditService.push_safe_from_kwargs",
            new_callable=AsyncMock,
        ) as mock_record:
            client = TestClient(app)
            response = client.post(
                "/xinyi/internal/audit",
                headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
                json={
                    "user_id": str(uuid.uuid4()),
                    "action": "hm.tenant.create",
                    "resource_type": "tenant", "resource_id": "abc",
                    "detail": {"name": "x"}, "ip_address": "127.0.0.1",
                    "occurred_at": "2026-06-22T00:00:00+00:00",
                },
            )
        assert response.status_code == 202
        mock_record.assert_called_once()
    finally:
        teardown()


def test_push_event_user_null_ok():
    teardown = _setup_overrides()
    try:
        with patch(
            "xinyi_platform.api.internal.AuditService.push_safe_from_kwargs",
            new_callable=AsyncMock,
        ):
            client = TestClient(app)
            response = client.post(
                "/xinyi/internal/audit",
                headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
                json={
                    "user_id": None,
                    "action": "system.task",
                    "resource_type": "system", "resource_id": "-",
                },
            )
        assert response.status_code == 202
    finally:
        teardown()
