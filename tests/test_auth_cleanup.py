"""پاک‌سازی نشست‌های مرده و تلاش‌های ورود قدیمی (مرحله ۲)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.auth.maintenance import cleanup_auth_state
from backend.database.models.user import LoginAttempt, User, UserSession
from tests.conftest import TestingSession


def _session(user_id, token: str, **kwargs) -> UserSession:
    return UserSession(user_id=user_id, token_hash=token * 64, csrf_hash="c" * 64, **kwargs)


def test_cleanup_removes_only_stale_rows() -> None:
    db = TestingSession()
    now = datetime.now(UTC)
    try:
        user = User(username="cleanup", password_hash="x", role="viewer")
        db.add(user)
        db.commit()

        live = _session(user.id, "a", expires_at=now + timedelta(days=1))
        expired = _session(user.id, "b", expires_at=now - timedelta(days=30))
        revoked_old = _session(
            user.id,
            "d",
            expires_at=now + timedelta(days=1),
            revoked_at=now - timedelta(days=30),
        )
        revoked_fresh = _session(
            user.id,
            "e",
            expires_at=now + timedelta(days=1),
            revoked_at=now - timedelta(hours=1),
        )
        db.add_all([live, expired, revoked_old, revoked_fresh])
        db.add_all([
            LoginAttempt(ip="1.1.1.1", username="cleanup",
                         created_at=now - timedelta(days=30)),
            LoginAttempt(ip="1.1.1.1", username="cleanup", created_at=now),
        ])
        db.commit()

        removed = cleanup_auth_state(db, now=now)

        assert removed == {"sessions": 2, "login_attempts": 1}
        remaining = set(db.execute(select(UserSession.token_hash)).scalars())
        assert remaining == {"a" * 64, "e" * 64}
        assert len(db.execute(select(LoginAttempt)).scalars().all()) == 1
    finally:
        db.close()


def test_cleanup_is_idempotent() -> None:
    db = TestingSession()
    try:
        assert cleanup_auth_state(db) == {"sessions": 0, "login_attempts": 0}
        assert cleanup_auth_state(db) == {"sessions": 0, "login_attempts": 0}
    finally:
        db.close()
