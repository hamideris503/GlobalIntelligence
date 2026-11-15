"""تست allow/deny برای عملیات حساس مدیریتی (WP-04.2).

هدف: اثبات اینکه گیت نقش واقعاً در مسیر درخواست اجرا می‌شود، نه فقط در تابع
`required_role`. برای هر مسیر حساس سه حالت بررسی می‌شود:

- viewer  → 403 با `error.details.required = "admin"`
- analyst → 403 (اجرای تحلیل کافی نیست)
- admin   → هر پاسخی به‌جز 403 (نبود داده یا اعتبارسنجی ورودی مجاز است)

هیچ ارسال واقعی انجام نمی‌شود: `dry_run=true` صریح پاس داده می‌شود و مقصد
شبکهٔ تست خالی است.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.main import app

TARGET_ID = "11111111-1111-1111-1111-111111111111"

# (method, path, json body) — عملیات حساسی که باید فقط admin باشد.
SENSITIVE: list[tuple[str, str, dict | None]] = [
    ("POST", "/api/settings/providers", {"name": "probe", "kind": "openai"}),
    ("POST", f"/api/settings/providers/{TARGET_ID}/key", {"api_key": "x"}),
    ("POST", f"/api/settings/models/{TARGET_ID}/verify", {"confirm": True}),
    ("PUT", "/api/settings/app", {}),
    ("POST", "/api/alerts/test-deliver/telegram", None),
    ("POST", "/api/dispatch/recover-screening", None),
    ("POST", "/api/archive/restore", {"archive_id": str(uuid.uuid4())}),
    ("POST", "/api/ingest/all", None),
    ("POST", "/api/jobs/trigger", {}),
]

ADMIN_READS = [
    "/api/settings/providers",
    "/api/settings/app",
    "/api/archive/storage",
    "/api/audit/records",
    "/api/ops/status",
]


@pytest.fixture
def as_role():
    def _set(role: str, *, email_verified: bool = True) -> None:
        app.dependency_overrides[require_user] = lambda: CurrentUser(
            username=role, role=role, via="session", email_verified=email_verified
        )

    yield _set
    app.dependency_overrides.pop(require_user, None)


def _call(client: TestClient, method: str, path: str, body: dict | None):
    kwargs = {"json": body} if body is not None else {}
    return client.request(method, path, **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), SENSITIVE)
def test_viewer_is_denied(client: TestClient, as_role, method: str, path: str, body) -> None:
    as_role("viewer")
    res = _call(client, method, path, body)
    assert res.status_code == 403, f"{method} {path} باید برای viewer 403 باشد"
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN"
    assert err["details"]["required"] == "admin"
    assert err["details"]["role"] == "viewer"
    assert err["details"]["path"] == path


@pytest.mark.parametrize(("method", "path", "body"), SENSITIVE)
def test_analyst_is_denied(client: TestClient, as_role, method: str, path: str, body) -> None:
    as_role("analyst")
    res = _call(client, method, path, body)
    assert res.status_code == 403, f"{method} {path} باید برای analyst 403 باشد"
    assert res.json()["error"]["details"]["required"] == "admin"


@pytest.mark.parametrize(("method", "path", "body"), SENSITIVE)
def test_admin_passes_the_role_gate(client: TestClient, as_role, method: str, path: str, body) -> None:
    as_role("admin")
    res = _call(client, method, path, body)
    assert res.status_code != 403, f"{method} {path} نباید برای admin 403 باشد"


@pytest.mark.parametrize("path", ADMIN_READS)
def test_operational_reads_deny_viewer_allow_admin(client: TestClient, as_role, path: str) -> None:
    as_role("viewer")
    assert client.get(path).status_code == 403
    as_role("admin")
    assert client.get(path).status_code in (200, 409)


def test_disabled_session_bypass_still_yields_admin_key_path(monkeypatch) -> None:
    """X-API-Key معتبر همچنان نقش service/admin می‌گیرد (سازگاری n8n)."""
    monkeypatch.delenv("GI_ALLOW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("API_KEY", "matrix-key-123")
    from backend.core.config import get_settings

    get_settings.cache_clear()
    try:
        authed = TestClient(app, raise_server_exceptions=False)
        res = authed.get("/api/settings/providers", headers={"X-API-Key": "matrix-key-123"})
        assert res.status_code == 200
    finally:
        monkeypatch.setenv("GI_ALLOW_DEV_AUTH_BYPASS", "1")
        monkeypatch.setenv("API_KEY", "")
        get_settings.cache_clear()


def test_unverified_email_is_blocked_outside_auth(client: TestClient, as_role) -> None:
    as_role("viewer", email_verified=False)
    res = client.get("/api/sources")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
