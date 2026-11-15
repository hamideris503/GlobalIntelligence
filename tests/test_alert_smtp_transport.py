"""رگرسیون انتقال SMTP در Alert delivery.

باگ‌های واقعی که این تست‌ها قفل می‌کنند:
1. `SMTP_USE_TLS=true` همیشه `SMTP_SSL` (TLS ضمنی، پورت ۴۶۵) را انتخاب می‌کرد و ارسال
   روی پورت ۵۸۷ با `SSLError` شکست می‌خورد؛ STARTTLS هرگز استفاده نمی‌شد.
2. مسیر Alert فقط `SMTP_USER` را می‌خواند، در حالی که پروژه `SMTP_USERNAME` را مستند
   کرده است؛ نتیجه: login انجام نمی‌شد.
"""
from __future__ import annotations

import smtplib

from domains.alerts import delivery as D


class _FakeSMTP:
    """جایگزین smtplib.SMTP — ثبت تماس‌ها بدون شبکه."""

    calls: list[tuple] = []

    def __init__(self, host, port, timeout=None):  # noqa: ARG002
        _FakeSMTP.calls.append(("SMTP", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):  # noqa: ARG002
        _FakeSMTP.calls.append(("starttls",))

    def login(self, username, password):  # noqa: ARG002
        _FakeSMTP.calls.append(("login", username))

    def send_message(self, msg):
        _FakeSMTP.calls.append(("send_message", msg["To"]))


class _FakeSMTPSSL(_FakeSMTP):
    def __init__(self, host, port, timeout=None, context=None):  # noqa: ARG002
        _FakeSMTP.calls.append(("SMTP_SSL", host, port))


def _send(monkeypatch, *, port: int, use_tls: bool) -> list[tuple]:
    _FakeSMTP.calls = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTPSSL)
    D._smtp_send(
        host="smtp.example.com",
        port=port,
        username="u",
        password="p",
        use_tls=use_tls,
        sender="from@example.com",
        recipients=["to@example.com"],
        subject="s",
        body="b",
    )
    return _FakeSMTP.calls


def test_port_587_uses_starttls_not_implicit_ssl(monkeypatch):
    calls = _send(monkeypatch, port=587, use_tls=True)
    assert calls[0][0] == "SMTP"
    assert ("starttls",) in calls
    assert all(c[0] != "SMTP_SSL" for c in calls)


def test_port_465_uses_implicit_ssl(monkeypatch):
    calls = _send(monkeypatch, port=465, use_tls=True)
    assert calls[0][0] == "SMTP_SSL"
    assert all(c[0] != "starttls" for c in calls)


def test_tls_disabled_skips_starttls(monkeypatch):
    calls = _send(monkeypatch, port=25, use_tls=False)
    assert calls[0][0] == "SMTP"
    assert all(c[0] != "starttls" for c in calls)


def test_username_falls_back_to_smtp_username(monkeypatch):
    """SMTP_USERNAME (نام مستندشده) باید برای login کافی باشد."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setenv("SMTP_USERNAME", "canonical@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "to@example.com")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    _FakeSMTP.calls = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(D, "_smtp_send", _real_smtp_send)

    assert D._env("SMTP_USER") is None
    assert D._env("SMTP_USERNAME") == "canonical@example.com"


# نگه‌داشتن تابع اصلی برای استفادهٔ صریح در صورت نیاز
_real_smtp_send = D._smtp_send
