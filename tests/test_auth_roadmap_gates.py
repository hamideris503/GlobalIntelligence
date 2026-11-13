"""گیت‌های نقشه‌راه F03.UX.AUTH.

شش قراردادی که تا امروز فقط در کد بود و تست نداشت:
بازیابی رمز، ابطال نشست پس از تغییر رمز، نشست ادمین، نشست لغزان عادی،
توکن منقضی، و رفتار صادقانه وقتی SMTP تنظیم نشده است.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.auth.email import clear_sink, get_sink_messages
from backend.auth.passwords import hash_password
from backend.auth.sessions import (
    ADMIN_SESSION_DAYS,
    NORMAL_SESSION_DAYS,
    token_hash,
)
from backend.core.config import get_settings
from backend.database.models.user import AuthToken, User, UserSession
from tests.conftest import TestingSession, app

# پیام‌ها به‌جای ارسال واقعی در حافظه ضبط می‌شوند (sink در زمان فراخوانی خوانده می‌شود).
os.environ.setdefault("GI_EMAIL_SINK", "1")

API_KEY = "test-api-key-please-rotate"
PASSWORD = "OldPassword123456"
NEW_PASSWORD = "NewPassword123456"


@pytest.fixture
def keyed(monkeypatch) -> None:
    """کلید API تنظیم می‌شود تا مسیر dev bypass خاموش شود."""
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _make_user(username: str = "alice", role: str = "analyst", email: str | None = None) -> uuid.UUID:
    session = TestingSession()
    try:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(PASSWORD),
            role=role,
            active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
    finally:
        session.close()


def _login(client: TestClient, username: str = "alice", password: str = PASSWORD):
    return client.post("/api/auth/session", json={"username": username, "password": password})


def _csrf(client: TestClient) -> str:
    return client.cookies.get("gi_csrf") or ""


def _linked_token() -> str:
    match = re.search(r"token=([^\s]+)", get_sink_messages()[-1].get_content())
    assert match, "ایمیل بدون توکن ساخته شد"
    return match.group(1)


def _session_row(username: str = "alice") -> UserSession:
    session = TestingSession()
    try:
        user = session.query(User).filter(User.username == username).one()
        return session.query(UserSession).filter(UserSession.user_id == user.id).one()
    finally:
        session.close()


def test_password_reset_full_cycle(client: TestClient) -> None:
    """forgot → توکن از ایمیل → reset → ورود با رمز جدید → رد توکن مصرف‌شده."""
    clear_sink()
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "reset@example.com",
            "username": "resetuser",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert reg.status_code == 200, reg.text
    verify_token = _linked_token()
    assert client.get(f"/api/auth/verify-email?token={verify_token}").status_code == 200

    clear_sink()
    forgot = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200, forgot.text
    reset_token = _linked_token()
    assert reset_token != verify_token

    reset = client.post(
        "/api/auth/reset-password",
        json={
            "token": reset_token,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert reset.status_code == 200, reset.text

    assert _login(client, "resetuser", NEW_PASSWORD).status_code == 200
    assert _login(client, "resetuser", PASSWORD).status_code == 401

    reused = client.post(
        "/api/auth/reset-password",
        json={
            "token": reset_token,
            "password": "AnotherPassword123",
            "confirm_password": "AnotherPassword123",
        },
    )
    assert reused.status_code == 400
    assert reused.json()["detail"] == "invalid or expired token"


def test_change_password_revokes_other_sessions(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    first_token = client.cookies.get("gi_session")
    assert _login(client).status_code == 200
    second_token = client.cookies.get("gi_session")
    assert first_token and second_token and first_token != second_token

    other = TestClient(app)
    other.cookies.set("gi_session", first_token)

    changed = client.post(
        "/api/auth/change-password",
        json={
            "current_password": PASSWORD,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert changed.status_code == 200, changed.text

    # نشست دیگر (مرورگر دوم) باید سمت سرور ابطال شده باشد، نه فقط کوکی پاک شود.
    assert other.get("/api/auth/me").status_code == 401

    session = TestingSession()
    try:
        rows = session.query(UserSession).all()
        assert len(rows) == 2
        assert all(row.revoked_at is not None for row in rows)
    finally:
        session.close()

    assert _login(client, "alice", PASSWORD).status_code == 401
    assert _login(client, "alice", NEW_PASSWORD).status_code == 200


def test_admin_session_never_expires(client: TestClient, keyed) -> None:
    _make_user(username="root", role="admin")
    assert _login(client, "root").status_code == 200

    row = _session_row("root")
    assert row.expires_at is None

    # حتی ۳۱ روز بی‌فعالیتی نباید نشست ادمین را ببندد.
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.last_seen_at = datetime.now(UTC) - timedelta(days=31)
        session.commit()
    finally:
        session.close()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert _session_row("root").expires_at is None

    cookie = me.headers.get("set-cookie") or ""
    match = re.search(r"Max-Age=(\d+)", cookie, re.I)
    assert match is not None
    assert int(match.group(1)) == ADMIN_SESSION_DAYS * 24 * 60 * 60


def test_normal_session_slides_and_expires_on_inactivity(client: TestClient, keyed) -> None:
    user_id = _make_user(username="normal", role="viewer")
    assert _login(client, "normal").status_code == 200

    now = datetime.now(UTC)
    row = _session_row("normal")
    assert row.expires_at is not None
    assert _aware(row.expires_at) - now > timedelta(days=NORMAL_SESSION_DAYS - 1)

    # روز ۷: تمدید باید پنجره را ۳۰ روز دیگر جلو ببرد.
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.last_seen_at = now - timedelta(days=7)
        row.expires_at = now + timedelta(days=23)
        session.commit()
    finally:
        session.close()
    assert client.get("/api/auth/me").status_code == 200
    assert _aware(_session_row("normal").expires_at) - datetime.now(UTC) > timedelta(days=29)

    # روز ۳۶ (۲۹ روز پس از آخرین فعالیت): هنوز معتبر و دوباره تمدید می‌شود.
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.last_seen_at = datetime.now(UTC) - timedelta(days=29)
        row.expires_at = datetime.now(UTC) + timedelta(days=1)
        session.commit()
    finally:
        session.close()
    assert client.get("/api/auth/me").status_code == 200
    assert _aware(_session_row("normal").expires_at) - datetime.now(UTC) > timedelta(days=29)

    # مرز بی‌فعالیتی: یک دقیقه بعد از ۳۰ روز، نشست بسته است.
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.last_seen_at = datetime.now(UTC) - timedelta(days=30, minutes=1)
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    finally:
        session.close()
    assert client.get("/api/auth/me").status_code == 401

    # کاربر و رکوردش پاک نمی‌شوند؛ فقط نشست باطل است.
    session = TestingSession()
    try:
        assert session.get(User, user_id) is not None
        assert session.query(UserSession).count() == 1
    finally:
        session.close()
    assert _login(client, "normal").status_code == 200


def test_expired_verification_token_is_rejected(client: TestClient) -> None:
    user_id = _make_user(username="expired", role="viewer")
    raw = "expired-verification-token"
    session = TestingSession()
    try:
        session.add(
            AuthToken(
                user_id=user_id,
                purpose="verify_email",
                token_hash=token_hash(raw),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    finally:
        session.close()

    res = client.post("/api/auth/verify-email", json={"token": raw})
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid or expired token"

    session = TestingSession()
    try:
        assert session.get(User, user_id).email_verified is False
        assert session.query(AuthToken).one().used_at is None
    finally:
        session.close()


def test_missing_smtp_reports_not_configured_without_leaking_token(
    client: TestClient, monkeypatch
) -> None:
    from backend.api.routers import auth as auth_router
    from backend.auth.email import EmailDeliveryNotConfigured

    def fail(*args, **kwargs):
        raise EmailDeliveryNotConfigured("smtp not configured")

    monkeypatch.setattr(auth_router, "send_email", fail)
    clear_sink()

    reg = client.post(
        "/api/auth/register",
        json={
            "email": "nosmtp@example.com",
            "username": "nosmtp",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert body["email_sent"] is False
    assert body["code"] == "EMAIL_DELIVERY_NOT_CONFIGURED"
    # پاسخ نه توکن دارد و نه کلید token را حتی به‌صورت نام.
    assert "token" not in reg.text.lower()

    # حساب ساخته شده و ورود (پیش از تأیید ایمیل) کار می‌کند؛ موفقیت ساختگی گزارش نمی‌شود.
    login = _login(client, "nosmtp")
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email_verified"] is False
