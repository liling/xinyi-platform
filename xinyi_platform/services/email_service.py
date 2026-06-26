import asyncio
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from xinyi_platform.config import Settings

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailService:
    @staticmethod
    async def send(settings: Settings, *, to: list[str], subject: str, body: str, html: str | None = None) -> None:
        for addr in to:
            if not EMAIL_RE.match(addr):
                raise ValueError(f"Invalid email address: {addr!r}")

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))

        def _smtp_send():
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_from, to, msg.as_string())

        await asyncio.to_thread(_smtp_send)

    @staticmethod
    async def send_safe(settings: Settings, **kwargs) -> None:
        try:
            await EmailService.send(settings, **kwargs)
        except Exception as e:
            logger.error("Email send failed: %s", e)
