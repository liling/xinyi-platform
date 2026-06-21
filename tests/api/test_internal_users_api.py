import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.auth.internal_auth import verify_internal_client
from xinyi_platform.db import get_session
from xinyi_platform.main import app


def _setup_overrides(override_verify: bool = True):
    """Set up both verify_internal_client and get_session overrides. Returns teardown callable."""
    async def _fake_client():
        return MagicMock(client_id="test")

    async def _fake_session():
        session = MagicMock()
        session.execute = AsyncMock()
        session.execute.return_value = MagicMock()
        session.commit = AsyncMock()
        yield session

    if override_verify:
        app.dependency_overrides[verify_internal_client] = _fake_client
    app.dependency_overrides[get_session] = _fake_session

    def teardown():
        app.dependency_overrides.clear()
    return teardown


def test_batch_get_returns_users_dict():
    user_id_1 = uuid.uuid4()
    fake_batch = {
        user_id_1: {"id": str(user_id_1), "username": "alice", "display_name": "Alice",
                    "email": None, "role": "admin", "is_active": True},
    }
    teardown = _setup_overrides()
    try:
        with patch(
            "xinyi_platform.api.internal.UserService.batch_get",
            new_callable=AsyncMock, return_value=fake_batch,
        ):
            client = TestClient(app)
            response = client.post(
                "/internal/users/batch-get",
                headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
                json={"ids": [str(user_id_1)], "fields": ["username"]},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["users"][str(user_id_1)]["username"] == "alice"
    finally:
        teardown()


def test_batch_get_over_limit_returns_400():
    ids = [str(uuid.uuid4()) for _ in range(101)]
    teardown = _setup_overrides()
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/users/batch-get",
            headers={"X-Client-Id": "hm-prod", "X-Client-Secret": "x"},
            json={"ids": ids},
        )
        assert response.status_code == 400
    finally:
        teardown()


def test_batch_get_without_credentials_returns_401_or_422():
    """Missing X-Client-Id / X-Client-Secret headers → FastAPI returns 422 (missing required header)."""
    teardown = _setup_overrides(override_verify=False)
    try:
        client = TestClient(app)
        response = client.post("/internal/users/batch-get", json={"ids": []})
        assert response.status_code in (401, 422)
    finally:
        teardown()
