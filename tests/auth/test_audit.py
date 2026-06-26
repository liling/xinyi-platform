import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xinyi_platform.auth.audit import record_audit
from xinyi_platform.services.audit_service import AuditService


def _mock_request():
    req = MagicMock()
    req.client.host = "127.0.0.1"
    return req


@pytest.mark.asyncio
async def test_record_audit_swallows_db_failure():
    request = _mock_request()
    bad_factory = MagicMock()
    bad_factory.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    bad_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    with patch("xinyi_platform.auth.audit.get_session_factory", return_value=bad_factory):
        await record_audit(
            request,
            user_id=uuid.uuid4(),
            client_id="hm",
            action="test.action",
            resource_type="test",
            resource_id="123",
        )


@pytest.mark.asyncio
async def test_record_audit_skips_when_factory_missing():
    request = _mock_request()
    with patch("xinyi_platform.auth.audit.get_session_factory", return_value=None):
        await record_audit(
            request,
            user_id=uuid.uuid4(),
            client_id="hm",
            action="test.action",
            resource_type="test",
            resource_id="123",
        )


@pytest.mark.asyncio
async def test_push_safe_swallows_failure():
    bad_factory = MagicMock()
    bad_factory.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
    bad_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    await AuditService.push_safe(
        bad_factory,
        user_id=uuid.uuid4(),
        client_id="hm",
        action="test.action",
        resource_type="test",
        resource_id="123",
        detail=None,
        ip_address="127.0.0.1",
    )


@pytest.mark.asyncio
async def test_push_safe_from_kwargs_skips_when_factory_missing():
    with patch("xinyi_platform.db.get_session_factory", return_value=None):
        await AuditService.push_safe_from_kwargs(
            user_id=uuid.uuid4(),
            client_id="hm",
            action="test.action",
            resource_type="test",
            resource_id="123",
        )
