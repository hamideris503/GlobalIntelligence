"""نشست سمت سرور: توکن تصادفی، در DB فقط hash؛ محدودیت نرخ ورود پایدار در DB."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.database.models.user import LoginAttempt, User, UserSession

SESSION_COOKIE = "gi_session"
CSRF_COOKIE = "gi_csrf"
CSRF_HEADER = "X-CSRF-Token"

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 10
LAST_SEEN_REFRESH_SECONDS = 300


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    """SQLite تاریخ را بدون tz برمی‌گرداند؛ همه‌چیز UTC ذخیره شده است."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def create_session(
    db: Session,
    *,
    user: User,
    ip: str | None,
    user_agent: str | None,
    ttl_minutes: int,
) -> tuple[str, str]:
    """توکن‌های خام را برمی‌گرداند (فقط برای کوکی)؛ در DB فقط hash می‌ماند."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf_hash=token_hash(csrf),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            ip=(ip or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    db.commit()
    return token, csrf


def load_session(db: Session, token: str) -> tuple[UserSession, User] | None:
    row = db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if _aware(row.expires_at) <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        return None
    last_seen = row.last_seen_at
    if last_seen is None or (now - _aware(last_seen)).total_seconds() > LAST_SEEN_REFRESH_SECONDS:
        row.last_seen_at = now
        db.commit()
    return row, user


def revoke_session(db: Session, session_id: object) -> None:
    row = db.get(UserSession, session_id)
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()


def login_retry_after(db: Session, *, ip: str, username: str) -> int:
    """۰ = مجاز؛ در غیر این صورت ثانیه‌های باقی‌مانده تا تلاش مجاز (Retry-After)."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    stamps = (
        db.execute(
            select(LoginAttempt.created_at)
            .where(
                LoginAttempt.ip == ip,
                LoginAttempt.username == username,
                LoginAttempt.created_at >= cutoff,
            )
            .order_by(LoginAttempt.created_at)
        )
        .scalars()
        .all()
    )
    if len(stamps) < LOGIN_MAX_FAILURES:
        return 0
    unlock_at = _aware(stamps[0]) + timedelta(seconds=LOGIN_WINDOW_SECONDS)
    return max(1, int((unlock_at - now).total_seconds()) + 1)


def record_failed_login(db: Session, *, ip: str, username: str) -> None:
    now = datetime.now(UTC)
    db.add(LoginAttempt(ip=(ip or "")[:64], username=username[:128], created_at=now))
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < now - timedelta(days=1)))
    db.commit()
