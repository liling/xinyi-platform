import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from xinyi_platform.services.audit_service import AuditService


def _make_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_session():
    return _make_session()


async def test_push_persists(mock_session):
    log = await AuditService.push(
        mock_session,
        user_id=uuid.uuid4(),
        client_id="hm-prod",
        action="hm.tenant.create",
        resource_type="tenant",
        resource_id="abc-123",
        detail={"name": "Acme"},
        ip_address="127.0.0.1",
    )
    mock_session.add.assert_called_once()
    assert log.action == "hm.tenant.create"
    assert log.client_id == "hm-prod"


async def test_push_user_null_anonymous_ok(mock_session):
    log = await AuditService.push(
        mock_session,
        user_id=None,
        client_id=None,
        action="user.anonymous_event",
        resource_type="system",
        resource_id="-",
        detail=None,
        ip_address=None,
    )
    assert log.user_id is None
    assert log.client_id is None


async def test_query_returns_list(mock_session):
    fake_logs = [MagicMock(), MagicMock(), MagicMock()]
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = fake_logs
    mock_session.execute.return_value.scalars.return_value = scalars_mock

    result = await AuditService.query(mock_session, client_id="hm-prod", limit=50, offset=0)
    assert result == fake_logs


async def test_query_filter_by_user_id_and_time_range(mock_session):
    from datetime import datetime, timezone, timedelta
    since = datetime.now(timezone.utc) - timedelta(days=1)
    until = datetime.now(timezone.utc)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    mock_session.execute.return_value.scalars.return_value = scalars_mock

    result = await AuditService.query(
        mock_session,
        client_id=None,
        user_id=uuid.uuid4(),
        since=since,
        until=until,
        limit=50,
        offset=0,
    )
    assert result == []
