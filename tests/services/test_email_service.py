from unittest.mock import MagicMock, patch

import pytest

from xinyi_platform.config import Settings
from xinyi_platform.services.email_service import EmailService


@pytest.fixture
def settings():
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret="x" * 40,
        encryption_key="00112233445566778899aabbccddeeff",
        admin_password="x",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="postmaster@example.com",
        smtp_password="pwd",
        smtp_from="noreply@example.com",
    )


def test_send_email_smtp_success(settings):
    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = instance
        EmailService.send(settings, to=["user@example.com"], subject="Hi", body="Body")
        instance.sendmail.assert_called_once()
        args = instance.sendmail.call_args
        assert args[0][0] == "noreply@example.com"
        assert "user@example.com" in args[0][1]


def test_send_email_invalid_address_rejected(settings):
    with pytest.raises(ValueError):
        EmailService.send(settings, to=["not-an-email"], subject="x", body="x")


def test_send_email_smtp_failure_does_not_raise_to_caller(settings):
    with patch("smtplib.SMTP", side_effect=Exception("smtp down")):
        EmailService.send_safe(settings, to=["user@example.com"], subject="x", body="x")
