"""ارسال ایمیل: STARTTLS باید گواهی سرور را واقعاً اعتبارسنجی کند."""
import smtplib
import ssl

from backend.auth import email as email_mod
from backend.core.config import get_settings


def test_starttls_uses_verifying_ssl_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *args) -> bool:
            return False

        def starttls(self, context=None) -> None:
            captured["context"] = context

        def login(self, username: str, password: str) -> None:
            pass

        def send_message(self, msg) -> None:
            captured["sent"] = msg["To"]

    monkeypatch.delenv("GI_EMAIL_SINK", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_mod, "_sink_enabled", lambda: False)
    get_settings.cache_clear()
    try:
        email_mod.send_email("to@example.com", "subject", "body")
    finally:
        get_settings.cache_clear()

    ctx = captured["context"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert captured["sent"] == "to@example.com"
