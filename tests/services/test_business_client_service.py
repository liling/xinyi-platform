from unittest.mock import AsyncMock, MagicMock

import pytest

from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.business_client_service import BusinessClientService


def _make_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_session():
    return _make_session()


async def test_register_generates_id_and_secret(mock_session):
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    client, raw_secret = await BusinessClientService.register(
        mock_session,
        client_id="hm-prod",
        name="Hindsight Manager",
        redirect_uris=["http://hm:8001/auth/callback"],
    )
    assert client.client_id == "hm-prod"
    assert client.name == "Hindsight Manager"
    assert client.redirect_uris == ["http://hm:8001/auth/callback"]
    assert client.status == ClientStatus.ACTIVE
    assert isinstance(raw_secret, str)
    assert len(raw_secret) >= 32
    assert client.client_secret_hash != raw_secret


async def test_verify_secret_correct(mock_session):
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    client, raw_secret = await BusinessClientService.register(
        mock_session, client_id="hm", name="hm", redirect_uris=[],
    )

    mock_session.execute.return_value.scalar_one_or_none.return_value = client
    found = await BusinessClientService.verify_secret(mock_session, "hm", raw_secret)
    assert found is client


async def test_verify_secret_wrong(mock_session):
    client = BusinessClient(
        client_id="x", name="x", client_secret_hash="$2b$12$abcdefghijklmnopqrstuv",
        redirect_uris=[], status=ClientStatus.ACTIVE,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = client
    found = await BusinessClientService.verify_secret(mock_session, "x", "wrong-secret")
    assert found is None


async def test_verify_redirect_uri_in_whitelist(mock_session):
    client = BusinessClient(
        client_id="x", name="x", client_secret_hash="x",
        redirect_uris=["http://hm:8001/auth/callback", "http://localhost:8001/auth/callback"],
        status=ClientStatus.ACTIVE,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = client
    assert await BusinessClientService.verify_redirect_uri(mock_session, "x", "http://hm:8001/auth/callback") is True
    assert await BusinessClientService.verify_redirect_uri(mock_session, "x", "http://evil.com/cb") is False


async def test_disabled_client_cannot_authenticate(mock_session):
    client = BusinessClient(
        client_id="x", name="x", client_secret_hash="$2b$12$abcdefghijklmnopqrstuv",
        redirect_uris=[], status=ClientStatus.DISABLED,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = client
    assert await BusinessClientService.verify_secret(mock_session, "x", "anything") is None


async def test_register_or_update_creates_new():
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    client = await BusinessClientService.register_or_update(
        mock_session,
        client_id="hm-prod",
        name="Hindsight Manager",
        client_secret_hash="$2b$12$abc",
        redirect_uris=["http://hm:8001/callback"],
        logout_url="http://hm:8001/logout",
        base_url="http://hm:8001",
        home_path="/dashboard",
        description="RAG",
    )
    mock_session.add.assert_called_once()
    assert client.client_id == "hm-prod"
    assert client.base_url == "http://hm:8001"


async def test_register_or_update_updates_existing_metadata():
    existing = BusinessClient(
        client_id="hm-prod",
        name="Old Name",
        client_secret_hash="$2b$12$old",
        redirect_uris=["http://old"],
        logout_url=None,
        status=ClientStatus.ACTIVE,
    )
    existing.base_url = None
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
    mock_session.flush = AsyncMock()

    client = await BusinessClientService.register_or_update(
        mock_session,
        client_id="hm-prod",
        name="New Name",
        client_secret_hash="$2b$12$new",
        redirect_uris=["http://new"],
        logout_url="http://hm:8001/logout",
        base_url="http://hm:8001",
        home_path="/dashboard",
        description="RAG",
    )
    assert client.name == "New Name"
    assert client.base_url == "http://hm:8001"
    assert client.client_secret_hash == "$2b$12$old"  # NOT overwritten
    mock_session.add.assert_not_called()
