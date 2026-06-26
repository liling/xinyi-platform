from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from xinyi_platform.db import get_session
from xinyi_platform.main import app


@pytest.fixture
def cas_settings(monkeypatch):
    monkeypatch.setenv("XINYI_PLATFORM_CAS_SERVER_URL", "https://cas.example.com")
    monkeypatch.setenv("XINYI_PLATFORM_CAS_SERVICE_URL", "http://localhost:8000/cas/callback")


def test_cas_login_redirects_to_cas_server(cas_settings):
    client = TestClient(app)
    response = client.get("/xinyi/cas/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "cas.example.com/login" in response.headers["location"]


def test_cas_callback_invalid_ticket_returns_401(cas_settings):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    try:
        with patch(
            "xinyi_platform.api.cas.CASClient.verify_ticket",
            new_callable=AsyncMock, return_value=None,
        ):
            client = TestClient(app)
            response = client.get("/xinyi/cas/callback?ticket=bad", follow_redirects=False)
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
