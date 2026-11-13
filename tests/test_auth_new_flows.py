import os

os.environ.setdefault("GI_EMAIL_SINK", "1")

import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.auth.email import clear_sink, get_sink_messages
from backend.core.config import Settings, get_settings
from tests.conftest import app


def test_register_verify_login(client: TestClient) -> None:
    clear_sink()
    r = client.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "Password123456",
            "confirm_password": "Password123456",
        },
    )
    assert r.status_code == 200, r.text
    msgs = get_sink_messages()
    assert msgs
    m = re.search(r"token=([^\s]+)", msgs[-1].get_content())
    assert m
    tok = m.group(1)
    vr = client.get(f"/api/auth/verify-email?token={tok}")
    assert vr.status_code == 200, vr.text
    # reuse token fails
    vr2 = client.get(f"/api/auth/verify-email?token={tok}")
    assert vr2.status_code == 400
    lr = client.post("/api/auth/session", json={"username": "newuser", "password": "Password123456"})
    assert lr.status_code == 200, lr.text
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "newuser"
    assert me.json()["email_verified"] is True

def test_register_rejects_username_that_is_blank_after_strip(client: TestClient) -> None:
    for index, username in enumerate(("   ", "a  ")):
        r = client.post(
            "/api/auth/register",
            json={
                "email": f"short-{index}@example.com",
                "username": username,
                "password": "Password123456",
                "confirm_password": "Password123456",
            },
        )
        assert r.status_code == 422, r.text


def _register_unverified(client: TestClient, email: str, username: str) -> None:
    clear_sink()
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Password123456",
            "confirm_password": "Password123456",
        },
    )
    assert r.status_code == 200, r.text


def test_unverified_user_can_login_but_dashboard_is_blocked(client: TestClient) -> None:
    _register_unverified(client, "pending@example.com", "pendinguser")
    lr = client.post(
        "/api/auth/session",
        json={"username": "pendinguser", "password": "Password123456"},
    )
    assert lr.status_code == 200, lr.text
    assert lr.json()["user"]["email_verified"] is False
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email_verified"] is False
    blocked = client.get("/api/dashboard/overview")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_resend_verification_and_verify_unlocks_dashboard(client: TestClient) -> None:
    _register_unverified(client, "resend@example.com", "resenduser")
    lr = client.post(
        "/api/auth/session",
        json={"username": "resenduser", "password": "Password123456"},
    )
    assert lr.status_code == 200, lr.text
    assert client.get("/api/dashboard/overview").status_code == 403

    clear_sink()
    csrf = client.cookies.get("gi_csrf") or ""
    rs = client.post("/api/auth/resend-verification", headers={"X-CSRF-Token": csrf})
    assert rs.status_code == 200, rs.text
    assert rs.json()["email_sent"] is True
    body = get_sink_messages()[-1].get_content()
    m = re.search(r"token=([^\s]+)", body)
    assert m
    vr = client.post("/api/auth/verify-email", json={"token": m.group(1)})
    assert vr.status_code == 200, vr.text
    assert client.get("/api/auth/me").json()["email_verified"] is True
    assert client.get("/api/dashboard/overview").status_code == 200


def test_register_smtp_failure_returns_structured_warning(client: TestClient, monkeypatch) -> None:
    """خطای SMTP نباید بعد از ساخت حساب، پاسخ ۵۰۰ بدهد."""
    from backend.api.routers import auth as auth_router
    from backend.auth.email import EmailDeliveryFailed

    def fail(*args, **kwargs):
        raise EmailDeliveryFailed("smtp down")

    monkeypatch.setattr(auth_router, "send_email", fail)
    r = client.post(
        "/api/auth/register",
        json={
            "email": "smtpfail@example.com",
            "username": "smtpfail",
            "password": "Password123456",
            "confirm_password": "Password123456",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email_sent"] is False
    assert body["code"] == "EMAIL_DELIVERY_FAILED"

    # حساب ساخته شده و ورود (پیش از تأیید ایمیل) باید کار کند.
    lr = client.post(
        "/api/auth/session",
        json={"username": "smtpfail", "password": "Password123456"},
    )
    assert lr.status_code == 200, lr.text
    assert lr.json()["user"]["email_verified"] is False


def test_resend_smtp_failure_returns_structured_warning(client: TestClient, monkeypatch) -> None:
    _register_unverified(client, "resendfail@example.com", "resendfail")
    lr = client.post(
        "/api/auth/session",
        json={"username": "resendfail", "password": "Password123456"},
    )
    assert lr.status_code == 200, lr.text
    csrf = client.cookies.get("gi_csrf") or ""

    from backend.api.routers import auth as auth_router
    from backend.auth.email import EmailDeliveryFailed

    def fail(*args, **kwargs):
        raise EmailDeliveryFailed("smtp down")

    monkeypatch.setattr(auth_router, "send_email", fail)
    rs = client.post("/api/auth/resend-verification", headers={"X-CSRF-Token": csrf})
    assert rs.status_code == 200, rs.text
    assert rs.json()["email_sent"] is False
    assert rs.json()["code"] == "EMAIL_DELIVERY_FAILED"


def test_register_is_rate_limited_per_ip(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REGISTER_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("AUTH_REGISTER_WINDOW_SECONDS", "3600")
    get_settings.cache_clear()
    settings = get_settings()
    for index in range(settings.auth_register_max_attempts):
        r = client.post(
            "/api/auth/register",
            json={
                "email": f"burst-{index}@example.com",
                "username": f"burst{index}",
                "password": "Password123456",
                "confirm_password": "Password123456",
            },
        )
        assert r.status_code == 200, r.text

    blocked = client.post(
        "/api/auth/register",
        json={
            "email": "burst-final@example.com",
            "username": "burstfinal",
            "password": "Password123456",
            "confirm_password": "Password123456",
        },
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_forgot_password_rate_limits_email_across_ips() -> None:
    email = "target@example.com"
    settings = get_settings()
    for index in range(settings.auth_forgot_password_max_attempts):
        ip_client = TestClient(app, client=(f"10.0.0.{index + 1}", 50000))
        r = ip_client.post("/api/auth/forgot-password", json={"email": email})
        assert r.status_code == 200, r.text

    blocked_client = TestClient(app, client=("10.0.0.99", 50000))
    blocked = blocked_client.post("/api/auth/forgot-password", json={"email": email})
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_resend_verification_is_rate_limited_per_user(client: TestClient) -> None:
    _register_unverified(client, "resend-limit@example.com", "resendlimit")
    lr = client.post(
        "/api/auth/session",
        json={"username": "resendlimit", "password": "Password123456"},
    )
    assert lr.status_code == 200, lr.text
    csrf = client.cookies.get("gi_csrf") or ""

    settings = get_settings()
    for _ in range(settings.auth_resend_verification_max_attempts):
        r = client.post("/api/auth/resend-verification", headers={"X-CSRF-Token": csrf})
        assert r.status_code == 200, r.text

    blocked = client.post("/api/auth/resend-verification", headers={"X-CSRF-Token": csrf})
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_auth_rate_limits_are_env_configurable(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REGISTER_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("AUTH_REGISTER_WINDOW_SECONDS", "120")
    monkeypatch.setenv("AUTH_FORGOT_PASSWORD_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("AUTH_FORGOT_PASSWORD_WINDOW_SECONDS", "600")
    monkeypatch.setenv("AUTH_RESEND_VERIFICATION_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("AUTH_RESEND_VERIFICATION_WINDOW_SECONDS", "900")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.auth_register_max_attempts == 7
    assert settings.auth_register_window_seconds == 120
    assert settings.auth_forgot_password_max_attempts == 4
    assert settings.auth_forgot_password_window_seconds == 600
    assert settings.auth_resend_verification_max_attempts == 2
    assert settings.auth_resend_verification_window_seconds == 900


@pytest.mark.parametrize(
    "field",
    [
        "auth_register_max_attempts",
        "auth_register_window_seconds",
        "auth_forgot_password_max_attempts",
        "auth_forgot_password_window_seconds",
        "auth_resend_verification_max_attempts",
        "auth_resend_verification_window_seconds",
    ],
)
def test_auth_rate_limit_settings_reject_non_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: 0})


def test_legacy_api_key_login_endpoint_is_removed(client: TestClient) -> None:
    """ADR-STEP1AUTH-2: کلید API فقط از هدر خوانده می‌شود، نه از مسیر ورود."""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 404
