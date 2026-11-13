"""ارسال ایمیل برای تأیید حساب و بازیابی.

در production بدون SMTP، ارسال رد می‌شود (EMAIL_DELIVERY_NOT_CONFIGURED).
در تست‌ها با GI_EMAIL_SINK=1 پیام‌ها در حافظه ضبط می‌شوند.
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

_SINK: list[EmailMessage] = []


class EmailDeliveryNotConfigured(Exception):
    pass


class EmailDeliveryFailed(Exception):
    """SMTP/transport failure after delivery was configured."""


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


def _sink_enabled() -> bool:
    return os.environ.get("GI_EMAIL_SINK") == "1" or get_settings().email_sink_enabled


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if _sink_enabled():
        msg = EmailMessage()
        msg["To"] = to
        msg["From"] = settings.smtp_from or "no-reply@localhost"
        msg["Subject"] = subject
        msg.set_content(body)
        _SINK.append(msg)
        return

    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryNotConfigured("email delivery is not configured")

    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = settings.smtp_from
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        # Do not leak the recipient or message body into logs.
        logger.warning("email delivery failed | type=%s", type(exc).__name__)
        raise EmailDeliveryFailed("email delivery failed") from exc


def get_sink_messages() -> list[EmailMessage]:
    return list(_SINK)


def clear_sink() -> None:
    _SINK.clear()


def last_sink_body() -> str | None:
    if not _SINK:
        return None
    return _SINK[-1].get_content()