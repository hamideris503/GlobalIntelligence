import os

os.environ.setdefault("GI_EMAIL_SINK", "1")

import re

from fastapi.testclient import TestClient

from backend.auth.email import clear_sink, get_sink_messages


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
