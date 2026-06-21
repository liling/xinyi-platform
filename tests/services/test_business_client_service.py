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
