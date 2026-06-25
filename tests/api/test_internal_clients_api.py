from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xinyi_platform.api.internal_clients import router
from xinyi_platform.auth.internal_auth import verify_internal_client, verify_registration_token


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/xinyi")
    return app


def _make_mock_session(client=None, clients_list=None):
    session = MagicMock()
    result = MagicMock()
    if client is not None:
        result.scalar_one_or_none = MagicMock(return_value=client)
    if clients_list is not None:
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=clients_list)))
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def test_register_valid_token():
    mock_client = MagicMock()
    mock_client.client_id = "hm-prod"
    mock_client.name = "HM"
    mock_session = _make_mock_session(client=mock_client)

    app = _make_app()

    from xinyi_platform.db import get_session as real_get_session

    async def _fake_session():
        yield mock_session
    app.dependency_overrides[real_get_session] = _fake_session
    app.dependency_overrides[verify_registration_token] = lambda: "tok"

    with patch("xinyi_platform.api.internal_clients.BusinessClientService") as mock_svc:
        mock_svc.register_or_update = AsyncMock(return_value=mock_client)
        with patch("xinyi_platform.api.internal_clients.derive_client_secret", return_value="derived-secret"):
            with patch("xinyi_platform.api.internal_clients.bcrypt") as mock_bcrypt:
                mock_bcrypt.hashpw.return_value = b"$2b$12$hash"
                mock_bcrypt.gensalt.return_value = b"$2b$12$salt"

                client = TestClient(app)
                resp = client.post("/xinyi/internal/clients/register", json={
                    "client_id": "hm-prod",
                    "name": "Hindsight Manager",
                    "redirect_uris": ["http://hm:8001/callback"],
                    "base_url": "http://hm:8001",
                    "home_path": "/dashboard",
                    "description": "RAG",
                })
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"


def test_register_invalid_token():
    app = _make_app()
    client = TestClient(app)
    resp = client.post("/xinyi/internal/clients/register",
                       json={"client_id": "x"},
                       headers={"X-Registration-Token": "wrong"})
    assert resp.status_code == 401


def test_active_clients_returns_list():
    mock_client = MagicMock()
    mock_client.client_id = "hm-prod"
    mock_client.name = "HM"
    mock_client.base_url = "http://hm:8001"
    mock_client.home_path = "/dashboard"
    mock_client.description = "RAG"
    mock_client.logo_url = None
    mock_client.status = MagicMock(value="active")

    app = _make_app()
    mock_session = _make_mock_session(clients_list=[mock_client])

    from xinyi_platform.db import get_session as real_get_session
    from xinyi_platform.auth.internal_auth import verify_internal_client as real_verify

    async def _fake_session():
        yield mock_session
    app.dependency_overrides[real_get_session] = _fake_session
    app.dependency_overrides[real_verify] = lambda: mock_client

    client = TestClient(app)
    resp = client.get("/xinyi/internal/clients/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["clients"]) == 1
    assert data["clients"][0]["client_id"] == "hm-prod"


def test_active_clients_requires_auth():
    app = _make_app()
    from xinyi_platform.db import get_session as real_get_session
    async def _fake_session():
        yield MagicMock()
    app.dependency_overrides[real_get_session] = _fake_session
    client = TestClient(app)
    resp = client.get("/xinyi/internal/clients/active")
    assert resp.status_code == 422
