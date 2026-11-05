"""Auth API — نشست واقعی کاربر (مرحله ۱) + ورود قدیمی سازگار (deprecated).

- POST   /api/auth/session  → ورود با نام کاربری/رمز، کوکی HttpOnly + CSRF
- DELETE /api/auth/session  → خروج و ابطال نشست
- GET    /api/auth/me       → هویت فعلی (نشست یا سرویس)
- POST   /api/auth/login    → نسخه‌ی قدیمی که API_KEY را برمی‌گرداند (deprecated)

محدودیت نرخ ورود در DB است (login_attempts) تا با چند worker هم کار کند.
"""
from __future__ import annotations

import secrets

from domains.audit.service import log_action
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.deps import CurrentUser, require_user
from backend.auth.passwords import dummy_verify, verify_password
from backend.auth.sessions import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    create_session,
    login_retry_after,
    record_failed_login,
    revoke_session,
)
from backend.core.config import get_settings
from backend.database.models.user import User
from backend.database.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_CREDENTIALS = "نام کاربری یا رمز اشتباه است"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    ok: bool
    api_key: str = ""


class UserRead(BaseModel):
    username: str
    role: str
    via: str


class SessionResponse(BaseModel):
    ok: bool = True
    user: UserRead


class OkResponse(BaseModel):
    ok: bool = True


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def _set_session_cookies(
    response: Response, request: Request, token: str, csrf: str
) -> None:
    ttl_minutes = get_settings().session_ttl_minutes
    max_age = ttl_minutes * 60
    secure = _is_https(request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    # CSRF باید برای JS خواندنی باشد تا در هدر X-CSRF-Token برگردد.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _check_rate_limit(db: Session, request: Request, username: str) -> None:
    retry_after = login_retry_after(db, ip=_client_ip(request), username=username)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="too many login attempts; retry later",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/session", response_model=SessionResponse)
def create_session_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    _check_rate_limit(db, request, payload.username)
    user = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()

    if user is None or not user.active:
        dummy_verify(payload.password)  # زمان پاسخ مشابه کاربر موجود
        valid = False
    else:
        valid = verify_password(user.password_hash, payload.password)

    if not valid:
        record_failed_login(db, ip=_client_ip(request), username=payload.username)
        log_action(
            db,
            action="auth.login",
            actor="anonymous",
            target_type="user",
            target_id=payload.username,
            status="failed",
        )
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    settings = get_settings()
    token, csrf = create_session(
        db,
        user=user,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=settings.session_ttl_minutes,
    )
    _set_session_cookies(response, request, token, csrf)
    log_action(db, action="auth.login", actor=user.username, result={"via": "session"})
    return SessionResponse(user=UserRead(username=user.username, role=user.role, via="session"))


@router.delete("/session", response_model=OkResponse)
def delete_session_endpoint(
    request: Request,
    response: Response,
    current: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    if current.session_id is not None:
        revoke_session(db, current.session_id)
        log_action(db, action="auth.logout", actor=current.username)
    _clear_session_cookies(response)
    return OkResponse()


@router.get("/me", response_model=UserRead)
def me(current: CurrentUser = Depends(require_user)) -> UserRead:
    return UserRead(username=current.username, role=current.role, via=current.via)


@router.post("/login", response_model=LoginResponse, deprecated=True)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """منسوخ: به‌جای این از POST /api/auth/session استفاده کنید (فقط سازگاری)."""
    _check_rate_limit(db, request, payload.username)
    settings = get_settings()
    user_ok = secrets.compare_digest(payload.username, settings.admin_username or "")
    pass_ok = secrets.compare_digest(payload.password, settings.admin_password or "")
    if not (user_ok and pass_ok):
        record_failed_login(db, ip=_client_ip(request), username=payload.username)
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    return LoginResponse(ok=True, api_key=settings.api_key or "")
