from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app
from xinyi_platform.models.business_client import BusinessClient, ClientStatus


def _override_session(scalar_result=None, scalars_result=None):
    from unittest.mock import MagicMock
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = scalar_result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_result or []
    session.execute.return_value.scalars.return_value = scalars_mock
    session.commit = AsyncMock()

    async def _override():
        yield session
    return _override


def test_list_clients_renders():
    app.dependency_overrides[get_session] = _override_session(scalars_result=[])
    try:
        from xinyi_platform.auth.session import create_access_token
        from xinyi_platform.config import Settings
        s = Settings()
        token = create_access_token(
            sub="u-1", username="admin", role="admin",
            client_id="xinyi-platform-self",
            secret=s.jwt_secret, ttl_seconds=900,
        )
        client = TestClient(app)
        response = client.get("/admin/clients", cookies={"xinyi_session": token})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_register_client_returns_secret():
    fake = BusinessClient(
        id="00000000-0000-0000-0000-000000000001",
        client_id="test-cli", name="Test",
        client_secret_hash="x",
        redirect_uris=["http://x/cb"],
        status=ClientStatus.ACTIVE,
    )
    with patch(
        "xinyi_platform.api.admin_clients.BusinessClientService.register",
        new_callable=AsyncMock, return_value=(fake, "raw-secret"),
    ):
        app.dependency_overrides[get_session] = _override_session()
        try:
            from xinyi_platform.auth.session import create_access_token
            from xinyi_platform.config import Settings
            s = Settings()
            token = create_access_token(
                sub="u-1", username="admin", role="admin",
                client_id="xinyi-platform-self",
                secret=s.jwt_secret, ttl_seconds=900,
            )
            client = TestClient(app)
            response = client.post(
                "/admin/clients",
                cookies={"xinyi_session": token},
                json={"client_id": "test-cli", "name": "Test", "redirect_uris": ["http://x/cb"]},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["client_secret"] == "raw-secret"
        finally:
            app.dependency_overrides.clear()
