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

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from backend.api.errors import ApiError
from backend.auth.sessions import CSRF_HEADER, SESSION_COOKIE, load_session, token_hash
from backend.core.config import get_settings
from backend.database.session import get_db

ROLE_RANK: dict[str, int] = {"viewer": 1, "analyst": 2, "admin": 3}
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# POSTهایی که «اجرای تحلیل/استخراج» هستند و analyst هم می‌تواند اجرا کند.
ANALYST_WRITE_PATHS = frozenset({
    "/api/ai/chat",
    "/api/ai/generate",
    "/api/alerts/evaluate",
    "/api/audit/log",
    "/api/audit/replay",
    "/api/briefings/daily",
    "/api/briefings/weekly",
    "/api/claims/evidence",
    "/api/claims/extract",
    "/api/classify/run",
    "/api/debate/run",
    "/api/decisions/from-debate",
    "/api/decisions/run",
    "/api/dedup/run",
    "/api/dispatch/run",
    "/api/economic/fetch",
    "/api/events/extract",
    "/api/evaluation/run",
    "/api/forecasts/run",
    "/api/geopolitics/analyze",
    "/api/graph/extract",
    "/api/independence/run",
    "/api/iran/transmission/analyze",
    "/api/learning/run",
    "/api/macro/analyze",
    "/api/markets/fetch",
    "/api/narratives/build",
    "/api/outcomes/resolve",
    "/api/performance/record",
    "/api/research/graphrag",
    "/api/risk/analyze",
    "/api/scenarios/run",
    "/api/screening/screen",
    "/api/self-eval/run",
    "/api/society/analyze",
    "/api/tournaments/run",
    "/api/world-state/build",
})
ANALYST_WRITE_PREFIXES = ("/api/screening/review",)
# خواندن این بخش‌ها اطلاعات عملیاتی/اعتبارنامه است، نه داده‌ی تحلیلی.
ADMIN_READ_PREFIXES = (
    "/api/settings",
    "/api/archive",
    "/api/audit",
    "/api/local-runtimes",
    "/api/ops",
)


def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def required_role(method: str, path: str) -> str:
    """حداقل نقش لازم برای یک درخواست (منبع `docs/ROLE_MATRIX.md`)."""
    if method in SAFE_METHODS:
        return "admin" if _under(path, ADMIN_READ_PREFIXES) else "viewer"
    if path in ANALYST_WRITE_PATHS or _under(path, ANALYST_WRITE_PREFIXES):
        return "analyst"
    return "admin"


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
        raise ApiError(401, "INVALID_API_KEY", "invalid or missing API key")

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        if _dev_bypass_active():
            return CurrentUser(username="service", role="admin", via="api_key")
        raise ApiError(401, "AUTH_REQUIRED", "authentication required")

    loaded = load_session(db, token)
    if loaded is None:
        raise ApiError(401, "AUTH_REQUIRED", "session expired or revoked")
    session, user = loaded

    if request.method not in SAFE_METHODS:
        if not x_csrf_token or not secrets.compare_digest(
            token_hash(x_csrf_token), session.csrf_hash
        ):
            raise ApiError(403, "FORBIDDEN", "CSRF token missing or invalid")

    return CurrentUser(
        username=user.username, role=user.role, via="session", session_id=session.id
    )


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """نقش‌های خواسته‌شده یا بالاتر (viewer < analyst < admin)."""
    minimum = min((ROLE_RANK.get(r, 99) for r in roles), default=99)

    def dependency(current: CurrentUser = Depends(require_user)) -> CurrentUser:
        if ROLE_RANK.get(current.role, 0) < minimum:
            raise ApiError(
                403,
                "FORBIDDEN",
                "insufficient role",
                details={"required": next(
                    (r for r, rank in ROLE_RANK.items() if rank == minimum), "admin")},
            )
        return current

    return dependency


def access_guard(
    request: Request, current: CurrentUser = Depends(require_user)
) -> CurrentUser:
    """سیاست نقش سراسری بر اساس متد و مسیر (نگاشت در `docs/ROLE_MATRIX.md`)."""
    needed = required_role(request.method, request.url.path)
    if ROLE_RANK.get(current.role, 0) < ROLE_RANK[needed]:
        raise ApiError(
            403,
            "FORBIDDEN",
            "insufficient role",
            details={
                "required": needed,
                "role": current.role,
                "path": request.url.path,
                "method": request.method,
            },
        )
    return current


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """سازگاری عقب‌رو: فقط کلید API (بدون نشست)."""
    settings = get_settings()
    expected = settings.api_key
    if not expected:
        if settings.app_env == "production":
            raise ApiError(500, "INTERNAL", "API_KEY not configured")
        return  # در development آزاد
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise ApiError(401, "INVALID_API_KEY", "invalid or missing API key")
