"""یکپارچگی نام‌های SMTP بین Auth و Alert delivery (WP-04.3).

Alert delivery از `SMTP_USER` می‌خواند و Auth از `SMTP_USERNAME`. قبل از این
اصلاح، تنظیم فقط یکی از دو نام باعث می‌شد مسیر دیگر بی‌صدا بدون login ایمیل
بفرستد (یا ارسال شکست بخورد).
"""
from __future__ import annotations

from backend.core.config import Settings


def _settings(monkeypatch, **env: str) -> Settings:
    # `_env_file=None` ضروری است: وگرنه مقادیر واقعی `.env` مالک هم خوانده می‌شوند
    # و تست نه ایزوله است و نه می‌تواند مقادیر را در پیام خطا افشا نکند.
    for key in ("SMTP_USER", "SMTP_USERNAME", "SMTP_HOST", "SMTP_FROM", "SMTP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_smtp_user_is_read_by_auth_config(monkeypatch) -> None:
    cfg = _settings(monkeypatch, SMTP_HOST="smtp.example.com", SMTP_USER="bot@example.com")
    assert cfg.smtp_username == "bot@example.com"
    assert cfg.smtp_username is not None


def test_smtp_username_wins_when_both_are_set(monkeypatch) -> None:
    cfg = _settings(
        monkeypatch,
        SMTP_HOST="smtp.example.com",
        SMTP_USER="alias@example.com",
        SMTP_USERNAME="canonical@example.com",
    )
    assert cfg.smtp_username == "canonical@example.com"


def test_missing_both_leaves_login_disabled(monkeypatch) -> None:
    cfg = _settings(monkeypatch, SMTP_HOST="smtp.example.com")
    assert cfg.smtp_username is None
