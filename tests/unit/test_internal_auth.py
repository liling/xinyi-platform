import pytest
from fastapi import HTTPException

from xinyi_platform.auth.internal_auth import verify_registration_token


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("xinyi_platform.auth.internal_auth.get_settings", lambda: type("S", (), {"registration_token": "valid-token-123"})())
    return "valid-token-123"


async def test_correct_token_passes(mock_settings):
    result = await verify_registration_token(x_registration_token="valid-token-123")
    assert result == "valid-token-123"


async def test_wrong_token_rejected(mock_settings):
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="wrong-token")
    assert exc.value.status_code == 401


async def test_empty_token_rejected(mock_settings):
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="")
    assert exc.value.status_code == 401


async def test_token_not_configured(monkeypatch):
    monkeypatch.setattr("xinyi_platform.auth.internal_auth.get_settings", lambda: type("S", (), {"registration_token": ""})())
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="anything")
    assert exc.value.status_code == 500
