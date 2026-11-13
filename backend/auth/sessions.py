"""نشست سمت سرور: توکن تصادفی، در DB فقط hash؛ محدودیت نرخ ورود پایدار در DB.

قانون نشست:
- کاربر عادی: expires_at = last_activity + 30 روز (لغزان).
- مدیر: expires_at = NULL (بدون انقضای خودکار به علت عدم فعالیت).
- تمدید خودکار با فاصلهٔ حداقل ۵ دقیقه برای جلوگیری از فشار DB.
"""
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

NORMAL_SESSION_DAYS = 30
ADMIN_SESSION_DAYS = 365


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def create_session(
    db: Session,
    *,
    user: User,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, str]:
    """توکن‌های خام را برمی‌گرداند (فقط برای کوکی)؛ در DB فقط hash می‌ماند.

    مدیر بدون انقضا؛ کاربر عادی ۳۰ روز.
    """
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    if user.role == "admin":
        expires_at = None
    else:
        expires_at = now + timedelta(days=NORMAL_SESSION_DAYS)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf_hash=token_hash(csrf),
            expires_at=expires_at,
            last_seen_at=now,
            ip=(ip or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    db.commit()
    return token, csrf


def load_session(
    db: Session, token: str
) -> tuple[UserSession, User, bool] | None:
    """None اگر نامعتبر. سومین مقدار: آیا last_seen/expires تمدید شد."""
    row = db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if row.expires_at is not None and _aware(row.expires_at) <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        return None

    refreshed = False
    last_seen = row.last_seen_at
    if last_seen is None or (now - _aware(last_seen)).total_seconds() > LAST_SEEN_REFRESH_SECONDS:
        row.last_seen_at = now
        if row.expires_at is not None:
            row.expires_at = now + timedelta(days=NORMAL_SESSION_DAYS)
        db.commit()
        refreshed = True
    return row, user, refreshed


def revoke_session(db: Session, session_id: object) -> None:
    row = db.get(UserSession, session_id)
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: object) -> None:
    rows = db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for r in rows:
        r.revoked_at = now
    db.commit()


def login_retry_after(db: Session, *, ip: str, username: str) -> int:
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
