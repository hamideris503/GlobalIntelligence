"""وابستگی‌های احراز هویت (مرحله ۱).

دو مسیر معتبر، در یک dependency:
- کوکی نشست سرور (UI) → هویت واقعی کاربر + CSRF برای متدهای تغییردهنده.
- هدر `X-API-Key` (n8n/اسکریپت‌ها) → نقش admin، actor="service"، بدون CSRF.

اگر `API_KEY` تنظیم نشده باشد، در development (فقط) همه‌چیز مجاز است تا
تست‌ها و اجرای لوکال مثل قبل کار کنند.
"""
from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, Request, Response
from sqlalchemy.orm import Session

from backend.api.errors import ApiError
from backend.auth.sessions import (
    ADMIN_SESSION_DAYS,
    CSRF_HEADER,
    NORMAL_SESSION_DAYS,
    SESSION_COOKIE,
    load_session,
    token_hash,
)
from backend.core.config import get_settings
from backend.database.models.user import User
from backend.database.session import get_db

ROLE_RANK: dict[str, int] = {"viewer": 1, "analyst": 2, "admin": 3, "service": 3}
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# POSTهایی که «اجرای تحلیل/استخراج» هستند و analyst هم می‌تواند اجرا کند.
ANALYST_WRITE_PATHS = frozenset({
    "/api/ai/chat",
    "/api/ai/generate",
    "/api/alerts/evaluate",
    "/api/analyses/request",
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
# مسیرهای دارای suffix (مثل /api/decisions/{id}/review) هم نوشتن تحلیل‌گرند.
ANALYST_WRITE_SUFFIXES = ("/review",)
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
    if path.startswith("/api/decisions/") and path.endswith(ANALYST_WRITE_SUFFIXES):
        return "analyst"
    return "admin"


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str
    via: str  # session | api_key
    session_id: uuid.UUID | None = None
    email_verified: bool = True


def _dev_bypass_active() -> bool:
    # فقط در تست‌ها و با تنظیم صریح محیط، bypass فعال است.
    # در اجرای عادی، API_KEY خالی هرگز هویت admin تولید نمی‌کند.
    if os.environ.get("GI_ALLOW_DEV_AUTH_BYPASS") != "1":
        return False
    settings = get_settings()
    return not settings.api_key and settings.app_env != "production"


def is_email_verified(user: User) -> bool:
    """حساب بدون ایمیل نیازی به تأیید ایمیل ندارد.

    همین تعریف باید در Login/me و access_guard مشترک باشد تا ادمین seed/CLI
    بدون ایمیل در UI به‌عنوان «تأییدنشده» قفل نشود.
    """
    return bool(user.email_verified) or not bool(user.email)


def _is_https_request(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def require_user(
    request: Request,
    response: Response,
    x_api_key: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """نشست معتبر یا X-API-Key معتبر؛ در غیر این صورت 401/403."""
    settings = get_settings()

    if x_api_key:
        if settings.api_key and secrets.compare_digest(x_api_key, settings.api_key):
            return CurrentUser(username="service", role="service", via="api_key")
        if _dev_bypass_active():
            return CurrentUser(username="service", role="service", via="api_key")
        raise ApiError(401, "INVALID_API_KEY", "invalid or missing API key")

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        if _dev_bypass_active():
            return CurrentUser(username="service", role="service", via="api_key")
        raise ApiError(401, "AUTH_REQUIRED", "authentication required")

    loaded = load_session(db, token)
    if loaded is None:
        raise ApiError(401, "AUTH_REQUIRED", "session expired or revoked")
    session, user, refreshed = loaded

    # تمدید کوکی پایدار در صورت تمدید نشست.
    if refreshed:
        try:
            days = NORMAL_SESSION_DAYS if user.role != "admin" else ADMIN_SESSION_DAYS
            max_age = days * 24 * 60 * 60
            # response ممکن است توسط FastAPI تزریق شده باشد.
            if response is not None:
                response.set_cookie(
                    SESSION_COOKIE,
                    token,
                    max_age=max_age,
                    httponly=True,
                    samesite="lax",
                    secure=_is_https_request(request),
                    path="/",
                )
        except Exception:
            pass

    if request.method not in SAFE_METHODS:
        if not x_csrf_token or not secrets.compare_digest(
            token_hash(x_csrf_token), session.csrf_hash
        ):
            raise ApiError(403, "FORBIDDEN", "CSRF token missing or invalid")

    return CurrentUser(
        username=user.username,
        role=user.role,
        via="session",
        session_id=session.id,
        email_verified=is_email_verified(user),
    )


def require_session_user(current: CurrentUser = Depends(require_user)) -> CurrentUser:
    """حساب کاربری واقعی از کوکی نشست؛ API Key هویت حساب نمی‌سازد."""
    if current.via != "session":
        raise ApiError(401, "AUTH_REQUIRED", "session required")
    return current


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
    path = request.url.path
    if current.via == "session" and not current.email_verified and not path.startswith("/api/auth/"):
        raise ApiError(
            403,
            "EMAIL_NOT_VERIFIED",
            "email verification required",
            details={"path": path},
        )
    needed = required_role(request.method, path)
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
