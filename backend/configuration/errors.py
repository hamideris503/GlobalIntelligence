"""Control-plane errors — هر خطا وضعیت HTTP خودش را حمل می‌کند."""
from __future__ import annotations


class ConfigurationError(Exception):
    """خطای پایهٔ control plane؛ پیام برای کاربر بی‌خطر است."""

    status_code = 422


class UnknownKind(ConfigurationError):
    """descriptor با این kind وجود ندارد."""

    status_code = 404


class NotFound(ConfigurationError):
    """instance یا revision پیدا نشد."""

    status_code = 404


class Conflict(ConfigurationError):
    """تعارض نسخه/وضعیت (optimistic locking یا گذار نامجاز)."""

    status_code = 409


class Invalid(ConfigurationError):
    """payload یا نتیجهٔ تست نامعتبر است."""

    status_code = 422


__all__ = ["ConfigurationError", "Conflict", "Invalid", "NotFound", "UnknownKind"]
