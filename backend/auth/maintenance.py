"""پاک‌سازی دوره‌ای وضعیت احراز هویت (مرحله ۲).

`startup` صدا می‌زند و idempotent است: نشست‌های منقضی/ابطال‌شده‌ی قدیمی‌تر از
دوره‌ی نگه‌داری و تلاش‌های ورود قدیمی حذف می‌شوند. دوره‌ی نگه‌داری عمداً صفر
نیست تا ردپای امنیتی (چه‌کسی کِی خارج شد) برای مدتی بماند.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from backend.database.models.user import LoginAttempt, UserSession

SESSION_RETENTION_DAYS = 7
LOGIN_ATTEMPT_RETENTION_DAYS = 7


def cleanup_auth_state(
    db: Session,
    *,
    now: datetime | None = None,
    session_retention_days: int = SESSION_RETENTION_DAYS,
    login_retention_days: int = LOGIN_ATTEMPT_RETENTION_DAYS,
) -> dict[str, int]:
    """حذف نشست‌های مرده و تلاش‌های ورود قدیمی؛ تعداد حذف‌شده‌ها را برمی‌گرداند."""
    now = now or datetime.now(UTC)
    session_cutoff = now - timedelta(days=session_retention_days)
    login_cutoff = now - timedelta(days=login_retention_days)

    sessions = db.execute(
        delete(UserSession).where(
            or_(
                UserSession.expires_at < session_cutoff,
                and_(
                    UserSession.revoked_at.is_not(None),
                    UserSession.revoked_at < session_cutoff,
                ),
            )
        )
    ).rowcount
    attempts = db.execute(
        delete(LoginAttempt).where(LoginAttempt.created_at < login_cutoff)
    ).rowcount
    db.commit()
    return {"sessions": sessions or 0, "login_attempts": attempts or 0}
