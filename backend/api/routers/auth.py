"""Auth API — نشست واقعی کاربر + ثبت‌نام + تأیید ایمیل + بازیابی حساب."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from domains.audit.service import log_action
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.deps import CurrentUser, is_email_verified, require_session_user
from backend.auth.email import EmailDeliveryFailed, EmailDeliveryNotConfigured, send_email
from backend.auth.passwords import dummy_verify, hash_password, verify_password
from backend.auth.sessions import (
    CSRF_COOKIE,
    FORGOT_MAX_ATTEMPTS,
    FORGOT_WINDOW_SECONDS,
    REGISTER_MAX_ATTEMPTS,
    REGISTER_WINDOW_SECONDS,
    RESEND_MAX_ATTEMPTS,
    RESEND_WINDOW_SECONDS,
    SESSION_COOKIE,
    create_session,
    login_retry_after,
    rate_limit_retry_after,
    record_auth_attempt,
    record_failed_login,
    revoke_all_user_sessions,
    revoke_session,
)
from backend.core.config import get_settings
from backend.database.models.user import AuthToken, User
from backend.database.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_CREDENTIALS = "نام کاربری یا رمز اشتباه است"
RESERVED_USERNAMES = {"admin", "system", "root", "support", "moderator"}


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not 3 <= len(v) <= 32:
            raise ValueError("invalid username length")
        if not all(c.isalnum() or c in "_-" for c in v):
            raise ValueError("invalid username characters")
        if v.lower() in RESERVED_USERNAMES:
            raise ValueError("reserved username")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("passwords do not match")
        return v


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=256)


class ResendVerificationResponse(BaseModel):
    ok: bool = True
    email_sent: bool = False
    code: str = ""


class ForgotUsernameRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=256)
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("passwords do not match")
        return v


class LoginResponse(BaseModel):
    ok: bool
    api_key: str = ""


class UserRead(BaseModel):
    username: str
    role: str
    via: str
    email: str | None = None
    email_verified: bool = False


class SessionResponse(BaseModel):
    ok: bool = True
    user: UserRead


class OkResponse(BaseModel):
    ok: bool = True


class RegisterResponse(BaseModel):
    ok: bool = True
    message: str
    email_sent: bool = False
    code: str = ""


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def _set_session_cookies(response: Response, request: Request, token: str, csrf: str) -> None:
    max_age = 30 * 24 * 60 * 60
    secure = _is_https(request)
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, samesite="lax", secure=secure, path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=max_age, httponly=False, samesite="lax", secure=secure, path="/")


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _check_rate_limit(db: Session, request: Request, username: str) -> None:
    retry_after = login_retry_after(db, ip=_client_ip(request), username=username)
    if retry_after:
        raise HTTPException(status_code=429, detail="too many login attempts; retry later", headers={"Retry-After": str(retry_after)})


def _rate_limit_key(scope: str, value: str) -> str:
    return f"{scope}:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _enforce_attempt_limit(
    db: Session,
    *,
    key: str,
    max_attempts: int,
    window_seconds: int,
    ip: str | None = None,
) -> None:
    retry_after = rate_limit_retry_after(
        db,
        key=key,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        ip=ip,
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="too many attempts; retry later",
            headers={"Retry-After": str(retry_after)},
        )


def _create_token(db: Session, user: User, purpose: str, ttl_minutes: int, ip: str | None) -> str:
    raw = secrets.token_urlsafe(32)
    from backend.auth.sessions import token_hash

    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            ip=ip,
        )
    )
    db.commit()
    return raw


def _consume_token(db: Session, raw: str, purpose: str) -> AuthToken | None:
    from backend.auth.sessions import token_hash

    row = db.execute(
        select(AuthToken).where(AuthToken.token_hash == token_hash(raw), AuthToken.purpose == purpose)
    ).scalar_one_or_none()
    if row is None or row.used_at is not None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo is not None else row.expires_at.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        return None
    return row


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> RegisterResponse:
    email = str(payload.email).strip().lower()
    username = payload.username.strip().lower()
    client_ip = _client_ip(request)
    email_key = _rate_limit_key("register", email)

    _enforce_attempt_limit(
        db,
        key="register:ip",
        ip=client_ip,
        max_attempts=REGISTER_MAX_ATTEMPTS,
        window_seconds=REGISTER_WINDOW_SECONDS,
    )
    _enforce_attempt_limit(
        db,
        key=email_key,
        ip="",
        max_attempts=REGISTER_MAX_ATTEMPTS,
        window_seconds=REGISTER_WINDOW_SECONDS,
    )
    record_auth_attempt(db, key="register:ip", ip=client_ip)
    record_auth_attempt(db, key=email_key, ip="")

    # uniqueness checks
    existing_email = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing_email is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    existing_user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="username already taken")

    user = User(
        username=username,
        email=email,
        email_verified=False,
        password_hash=hash_password(payload.password),
        role="viewer",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # email verification token (24h)
    email_sent = False
    delivery_code = ""
    try:
        raw_token = _create_token(db, user, "verify_email", 24 * 60, _client_ip(request))
        settings = get_settings()
        link = f"{settings.app_base_url.rstrip('/')}/verify-email?token={quote(raw_token)}"
        send_email(
            email,
            "تأیید حساب GlobalIntelligence",
            f"برای تأیید حساب خود روی لینک زیر کلیک کنید:\n{link}\n\nاین لینک تا ۲۴ ساعت معتبر است.",
        )
        email_sent = True
    except EmailDeliveryNotConfigured:
        # حساب ساخته شد اما تأیید ایمیل قابل ارسال نیست.
        delivery_code = "EMAIL_DELIVERY_NOT_CONFIGURED"
    except EmailDeliveryFailed:
        # SMTP ناپایدار نباید بعد از ساخت حساب پاسخ ۵۰۰ بدهد.
        delivery_code = "EMAIL_DELIVERY_FAILED"

    log_action(db, action="auth.register", actor=username, target_type="user", target_id=username, status="ok")
    return RegisterResponse(
        ok=True,
        message="registration successful; verify your email",
        email_sent=email_sent,
        code=delivery_code,
    )


@router.get("/verify-email", response_model=OkResponse)
def verify_email(token: str, db: Session = Depends(get_db)) -> OkResponse:
    row = _consume_token(db, token, "verify_email")
    if row is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid token")
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    row.used_at = datetime.now(UTC)
    db.commit()
    log_action(db, action="auth.verify_email", actor=user.username, status="ok")
    return OkResponse()


@router.post("/verify-email", response_model=OkResponse)
def verify_email_post(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> OkResponse:
    return verify_email(payload.token, db)


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    request: Request,
    current: CurrentUser = Depends(require_session_user),
    db: Session = Depends(get_db),
) -> ResendVerificationResponse:
    if current.via != "session":
        raise HTTPException(status_code=403, detail="session required")
    client_ip = _client_ip(request)
    user_key = _rate_limit_key("resend_verification", current.username)
    _enforce_attempt_limit(
        db,
        key=user_key,
        max_attempts=RESEND_MAX_ATTEMPTS,
        window_seconds=RESEND_WINDOW_SECONDS,
    )
    record_auth_attempt(db, key=user_key, ip=client_ip)
    user = db.execute(select(User).where(User.username == current.username)).scalar_one_or_none()
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="authentication required")
    if is_email_verified(user):
        return ResendVerificationResponse(ok=True, email_sent=False, code="ALREADY_VERIFIED")
    try:
        raw_token = _create_token(db, user, "verify_email", 24 * 60, _client_ip(request))
        settings = get_settings()
        link = f"{settings.app_base_url.rstrip('/')}/verify-email?token={quote(raw_token)}"
        send_email(
            user.email,
            "تأیید حساب GlobalIntelligence",
            f"برای تأیید حساب خود روی لینک زیر کلیک کنید:\n{link}\n\nاین لینک تا ۲۴ ساعت معتبر است.",
        )
        return ResendVerificationResponse(ok=True, email_sent=True)
    except EmailDeliveryNotConfigured:
        return ResendVerificationResponse(
            ok=True, email_sent=False, code="EMAIL_DELIVERY_NOT_CONFIGURED"
        )
    except EmailDeliveryFailed:
        return ResendVerificationResponse(
            ok=True, email_sent=False, code="EMAIL_DELIVERY_FAILED"
        )


@router.post("/forgot-username", response_model=OkResponse)
def forgot_username(payload: ForgotUsernameRequest, request: Request, db: Session = Depends(get_db)) -> OkResponse:
    email = str(payload.email).strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None and user.active and user.email_verified:
        try:
            send_email(
                email,
                "نام کاربری شما در GlobalIntelligence",
                f"نام کاربری شما: {user.username}",
            )
        except (EmailDeliveryNotConfigured, EmailDeliveryFailed):
            pass
    # پاسخ یکسان
    return OkResponse()


@router.post("/forgot-password", response_model=OkResponse)
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)) -> OkResponse:
    email = str(payload.email).strip().lower()
    client_ip = _client_ip(request)
    email_key = _rate_limit_key("forgot_password", email)
    _enforce_attempt_limit(
        db,
        key="forgot_password:ip",
        ip=client_ip,
        max_attempts=FORGOT_MAX_ATTEMPTS,
        window_seconds=FORGOT_WINDOW_SECONDS,
    )
    _enforce_attempt_limit(
        db,
        key=email_key,
        ip="",
        max_attempts=FORGOT_MAX_ATTEMPTS,
        window_seconds=FORGOT_WINDOW_SECONDS,
    )
    record_auth_attempt(db, key="forgot_password:ip", ip=client_ip)
    record_auth_attempt(db, key=email_key, ip="")
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None and user.active and user.email_verified:
        try:
            raw_token = _create_token(db, user, "reset_password", 20, _client_ip(request))
            settings = get_settings()
            link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={quote(raw_token)}"
            send_email(
                email,
                "بازیابی رمز عبور GlobalIntelligence",
                f"برای بازنشانی رمز عبور روی لینک زیر کلیک کنید:\n{link}\n\nاین لینک تا ۲۰ دقیقه معتبر است.",
            )
        except (EmailDeliveryNotConfigured, EmailDeliveryFailed):
            pass
    return OkResponse()


@router.post("/reset-password", response_model=OkResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> OkResponse:
    row = _consume_token(db, payload.token, "reset_password")
    if row is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=400, detail="invalid token")
    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.now(UTC)
    row.used_at = datetime.now(UTC)
    db.commit()
    revoke_all_user_sessions(db, user.id)
    log_action(db, action="auth.reset_password", actor=user.username, status="ok")
    return OkResponse()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("passwords do not match")
        return v


@router.post("/change-password", response_model=OkResponse)
def change_password(payload: ChangePasswordRequest, request: Request, response: Response, current: CurrentUser = Depends(require_session_user), db: Session = Depends(get_db)) -> OkResponse:
    if current.via != "session" or current.session_id is None:
        raise HTTPException(status_code=403, detail="session required")
    user = db.execute(select(User).where(User.username == current.username)).scalar_one_or_none()
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="authentication required")
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=401, detail="current password is incorrect")
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="passwords do not match")
    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.now(UTC)
    db.commit()
    revoke_all_user_sessions(db, user.id)
    _clear_session_cookies(response)
    log_action(db, action="auth.change_password", actor=user.username, status="ok")
    return OkResponse()


@router.post("/session", response_model=SessionResponse)
def create_session_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    identifier = payload.username.strip()
    _check_rate_limit(db, request, identifier)

    # تشخیص ایمیل یا نام کاربری
    if "@" in identifier:
        user = db.execute(select(User).where(User.email == identifier.lower())).scalar_one_or_none()
    else:
        user = db.execute(select(User).where(User.username == identifier.lower())).scalar_one_or_none()

    if user is None or not user.active:
        dummy_verify(payload.password)
        valid = False
    else:
        valid = verify_password(user.password_hash, payload.password)

    if not valid:
        record_failed_login(db, ip=_client_ip(request), username=identifier)
        log_action(db, action="auth.login", actor="anonymous", target_type="user", target_id=identifier, status="failed")
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    token, csrf = create_session(db, user=user, ip=_client_ip(request), user_agent=request.headers.get("user-agent"))
    _set_session_cookies(response, request, token, csrf)
    log_action(db, action="auth.login", actor=user.username, result={"via": "session"})
    return SessionResponse(user=UserRead(username=user.username, role=user.role, via="session", email=user.email, email_verified=is_email_verified(user)))


@router.delete("/session", response_model=OkResponse)
def delete_session_endpoint(
    request: Request,
    response: Response,
    current: CurrentUser = Depends(require_session_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    if current.session_id is not None:
        revoke_session(db, current.session_id)
        log_action(db, action="auth.logout", actor=current.username)
    _clear_session_cookies(response)
    return OkResponse()


@router.get("/me", response_model=UserRead)
def me(current: CurrentUser = Depends(require_session_user), db: Session = Depends(get_db)) -> UserRead:
    user = None
    if current.via == "session":
        from sqlalchemy import select

        user = db.execute(select(User).where(User.username == current.username)).scalar_one_or_none()
    email = getattr(user, "email", None) if user else None
    verified = is_email_verified(user) if user else (current.via == "api_key")
    return UserRead(username=current.username, role=current.role, via=current.via, email=email, email_verified=verified)


@router.post("/login", response_model=LoginResponse, deprecated=True)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    _check_rate_limit(db, request, payload.username)
    settings = get_settings()
    user_ok = secrets.compare_digest(payload.username, settings.admin_username or "")
    pass_ok = secrets.compare_digest(payload.password, settings.admin_password or "")
    if not (user_ok and pass_ok):
        record_failed_login(db, ip=_client_ip(request), username=payload.username)
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    return LoginResponse(ok=True, api_key=settings.api_key or "")