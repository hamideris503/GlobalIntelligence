"""وابستگی‌های احراز هویت (مرحله ۱).

دو مسیر معتبر، در یک dependency:
- کوکی نشست سرور (UI) → هویت واقعی کاربر + CSRF برای متدهای تغییردهنده.
- هدر `X-API-Key` (n8n/اسکریپت‌ها) → نقش admin، actor="service"، بدون CSRF.

اگر `API_KEY` تنظیم نشده باشد، در development (فقط) همه‌چیز مجاز است تا
تست‌ها و اجرای لوکال مثل قبل کار کنند.
"""
from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.auth.sessions import CSRF_HEADER, SESSION_COOKIE, load_session, token_hash
from backend.core.config import get_settings
from backend.database.session import get_db

ROLE_RANK: dict[str, int] = {"viewer": 1, "analyst": 2, "admin": 3}
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str
    via: str  # session | api_key
    session_id: uuid.UUID | None = None


def _dev_bypass_active() -> bool:
    settings = get_settings()
    return not settings.api_key and settings.app_env != "production"


def require_user(
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """نشست معتبر یا X-API-Key معتبر؛ در غیر این صورت 401/403."""
    settings = get_settings()

    if x_api_key:
        if settings.api_key and secrets.compare_digest(x_api_key, settings.api_key):
            return CurrentUser(username="service", role="admin", via="api_key")
        if _dev_bypass_active():
            return CurrentUser(username="service", role="admin", via="api_key")
        raise HTTPException(status_code=401, detail="invalid or missing API key")

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        if _dev_bypass_active():
            return CurrentUser(username="service", role="admin", via="api_key")
        raise HTTPException(status_code=401, detail="authentication required")

    loaded = load_session(db, token)
    if loaded is None:
        raise HTTPException(status_code=401, detail="session expired or revoked")
    session, user = loaded

    if request.method not in SAFE_METHODS:
        if not x_csrf_token or not secrets.compare_digest(
            token_hash(x_csrf_token), session.csrf_hash
        ):
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

    return CurrentUser(
        username=user.username, role=user.role, via="session", session_id=session.id
    )


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """نقش‌های خواسته‌شده یا بالاتر (viewer < analyst < admin)."""
    minimum = min((ROLE_RANK.get(r, 99) for r in roles), default=99)

    def dependency(current: CurrentUser = Depends(require_user)) -> CurrentUser:
        if ROLE_RANK.get(current.role, 0) < minimum:
            raise HTTPException(status_code=403, detail="insufficient role")
        return current

    return dependency


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """سازگاری عقب‌رو: فقط کلید API (بدون نشست)."""
    settings = get_settings()
    expected = settings.api_key
    if not expected:
        if settings.app_env == "production":
            raise HTTPException(status_code=500, detail="API_KEY not configured")
        return  # در development آزاد
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")
