"""Tests for Stage 1 auth: server-side sessions, roles, CSRF, API-key compat."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.auth.bootstrap import seed_admin_user
from backend.auth.deps import require_role
from backend.auth.passwords import hash_password, verify_password
from backend.core.config import get_settings
from backend.database.models.user import LoginAttempt, User, UserSession
from backend.database.session import get_db
from tests.conftest import TestingSession, _override_get_db

API_KEY = "test-api-key-please-rotate"
PASSWORD = "pw-alice-123"


@pytest.fixture
def keyed(monkeypatch) -> None:
    """کلید API تنظیم می‌شود تا مسیر dev bypass خاموش شود و احراز هویت واقعاً سنجیده شود."""
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_user(username: str = "alice", role: str = "analyst", active: bool = True) -> None:
    session = TestingSession()
    try:
        session.add(
            User(
                username=username,
                password_hash=hash_password(PASSWORD),
                role=role,
                active=active,
            )
        )
        session.commit()
    finally:
        session.close()


def _login(client: TestClient, username: str = "alice", password: str = PASSWORD):
    return client.post(
        "/api/auth/session", json={"username": username, "password": password}
    )


def _csrf(client: TestClient) -> str:
    return client.cookies.get("gi_csrf") or ""


def test_login_creates_session_and_me(client: TestClient, keyed) -> None:
    _make_user()
    res = _login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["user"] == {"username": "alice", "role": "analyst", "via": "session"}
    assert "api_key" not in body

    cookies = res.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("gi_session="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    raw_token = client.cookies.get("gi_session")
    assert raw_token

    # در DB فقط hash ذخیره می‌شود، نه توکن خام.
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        assert row.token_hash != raw_token
        assert len(row.token_hash) == 64
        assert row.revoked_at is None
    finally:
        session.close()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_login_wrong_password_and_unknown_user(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client, password="wrong").status_code == 401
    assert _login(client, username="nobody").status_code == 401
    session = TestingSession()
    try:
        assert session.query(LoginAttempt).count() == 2
        assert session.query(UserSession).count() == 0
    finally:
        session.close()


def test_inactive_user_cannot_login(client: TestClient, keyed) -> None:
    _make_user(active=False)
    assert _login(client).status_code == 401


def test_logout_revokes_session_and_clears_cookie(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    res = client.delete("/api/auth/session", headers={"X-CSRF-Token": _csrf(client)})
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    session = TestingSession()
    try:
        assert session.query(UserSession).one().revoked_at is not None
    finally:
        session.close()


def test_csrf_required_for_cookie_writes(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    assert client.delete("/api/auth/session").status_code == 403
    assert client.delete(
        "/api/auth/session", headers={"X-CSRF-Token": "wrong"}
    ).status_code == 403
    assert client.get("/api/auth/me").status_code == 200  # سشن سالم ماند
    assert client.delete(
        "/api/auth/session", headers={"X-CSRF-Token": _csrf(client)}
    ).status_code == 200


def test_expired_session_rejected(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    finally:
        session.close()
    assert client.get("/api/auth/me").status_code == 401


def test_revoked_session_rejected(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    session = TestingSession()
    try:
        row = session.query(UserSession).one()
        row.revoked_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()
    assert client.get("/api/auth/me").status_code == 401


def test_role_guard_rejects_low_roles(client: TestClient, keyed) -> None:
    _make_user(role="viewer")
    assert _login(client).status_code == 200

    sub = FastAPI()

    @sub.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    def admin_only() -> dict:
        return {"ok": True}

    sub.dependency_overrides[get_db] = _override_get_db
    sub_client = TestClient(sub)
    sub_client.cookies.set("gi_session", client.cookies.get("gi_session"))

    assert sub_client.get("/admin-only").status_code == 403
    assert sub_client.get("/admin-only", headers={"X-API-Key": API_KEY}).status_code == 200


def test_api_key_compat_without_session(client: TestClient, keyed) -> None:
    me = client.get("/api/auth/me", headers={"X-API-Key": API_KEY})
    assert me.status_code == 200
    assert me.json() == {"username": "service", "role": "admin", "via": "api_key"}
    # یک endpoint محافظت‌شده‌ی معمولی هم باید با کلید کار کند.
    assert client.get("/api/audit/records", headers={"X-API-Key": API_KEY}).status_code == 200
    assert client.get("/api/audit/records").status_code == 401
    assert client.get(
        "/api/audit/records", headers={"X-API-Key": "nope"}
    ).status_code == 401


def test_dev_bypass_when_api_key_unset(client: TestClient) -> None:
    # conftest: API_KEY="" و APP_ENV=development → رفتار قبلی حفظ می‌شود.
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["via"] == "api_key"


def test_login_rate_limit_returns_429(client: TestClient, keyed) -> None:
    _make_user()
    for _ in range(10):
        assert _login(client, password="wrong").status_code == 401
    blocked = _login(client, password="wrong")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # حتی رمز درست هم در پنجره‌ی قفل رد می‌شود.
    assert _login(client).status_code == 429


def test_audit_actor_comes_from_session(client: TestClient, keyed) -> None:
    _make_user()
    assert _login(client).status_code == 200
    res = client.post(
        "/api/audit/log",
        json={"action": "stage1.test", "actor": "someone-else"},
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert res.status_code == 200
    assert res.json()["actor"] == "alice"


def test_seed_admin_is_idempotent_and_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("ADMIN_PASSWORD", "seed-pw-123")
    get_settings.cache_clear()
    session = TestingSession()
    try:
        seed_admin_user(session)
        seed_admin_user(session)
        users = session.query(User).all()
        assert len(users) == 1
        assert users[0].role == "admin"
        assert verify_password(users[0].password_hash, "seed-pw-123")
    finally:
        session.close()

    monkeypatch.delenv("ADMIN_USERNAME")
    monkeypatch.delenv("ADMIN_PASSWORD")
    get_settings.cache_clear()
    session = TestingSession()
    try:
        seed_admin_user(session)  # بدون env: فقط هشدار، بدون کاربر
        assert session.query(User).count() == 1
    finally:
        session.close()
