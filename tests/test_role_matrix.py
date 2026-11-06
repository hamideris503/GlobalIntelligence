"""ماتریس نقش (مرحله ۲): viewer / analyst / admin روی نمونه‌ی endpointها.

نگاشت کامل در `docs/ROLE_MATRIX.md` و منبع کد در `backend/auth/deps.py`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_role, require_user, required_role
from backend.core.config import get_settings
from backend.main import app


@pytest.fixture
def as_role():
    def _set(role: str) -> None:
        app.dependency_overrides[require_user] = lambda: CurrentUser(
            username=role, role=role, via="session"
        )

    yield _set
    app.dependency_overrides.pop(require_user, None)


@pytest.mark.parametrize(
    ("method", "path", "role"),
    [
        ("GET", "/api/sources", "viewer"),
        ("GET", "/api/events", "viewer"),
        ("GET", "/api/screening/queue", "viewer"),
        ("GET", "/api/settings/app", "admin"),
        ("GET", "/api/archive/catalog", "admin"),
        ("GET", "/api/audit/records", "admin"),
        ("GET", "/api/ops/metrics", "admin"),
        ("POST", "/api/sources", "admin"),
        ("PATCH", "/api/sources/abc", "admin"),
        ("POST", "/api/jobs/trigger", "admin"),
        ("POST", "/api/local-runtimes/status/kev/start", "admin"),
        ("POST", "/api/archive/restore", "admin"),
        ("DELETE", "/api/settings/providers/x", "admin"),
        ("POST", "/api/events/extract", "analyst"),
        ("POST", "/api/classify/run", "analyst"),
        ("POST", "/api/alerts/evaluate", "analyst"),
        ("POST", "/api/screening/review/abc/ack", "analyst"),
        ("POST", "/api/ai/chat", "analyst"),
    ],
)
def test_required_role_map(method: str, path: str, role: str) -> None:
    assert required_role(method, path) == role


def test_viewer_reads_but_cannot_write(client: TestClient, as_role) -> None:
    as_role("viewer")
    assert client.get("/api/sources").status_code == 200
    res = client.post("/api/sources", json={"name": "nope", "type": "rss"})
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["details"]["required"] == "admin"
    assert body["detail"] == body["error"]["message"]


def test_viewer_cannot_read_operational_settings(client: TestClient, as_role) -> None:
    as_role("viewer")
    assert client.get("/api/settings/providers").status_code == 403


def test_analyst_runs_analysis_but_not_admin_writes(client: TestClient, as_role) -> None:
    as_role("analyst")
    assert client.post("/api/events/extract").status_code == 200
    assert client.post("/api/ingest/all").status_code == 403
    assert client.get("/api/settings/providers").status_code == 403


def test_admin_session_can_write(client: TestClient, as_role) -> None:
    as_role("admin")
    res = client.post("/api/sources", json={"name": "admin-made", "type": "rss"})
    assert res.status_code == 201


def test_api_key_is_admin_and_still_works(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key-123")
    get_settings.cache_clear()
    authed = TestClient(app, raise_server_exceptions=False)
    created = authed.post(
        "/api/sources",
        json={"name": "via-key", "type": "rss"},
        headers={"X-API-Key": "test-key-123"},
    )
    assert created.status_code == 201
    assert authed.get(
        "/api/settings/providers", headers={"X-API-Key": "test-key-123"}
    ).status_code == 200


def test_require_role_rejects_lower_role() -> None:
    from backend.api.errors import ApiError

    guard = require_role("admin")
    with pytest.raises(ApiError) as exc:
        guard(CurrentUser(username="v", role="viewer", via="session"))
    assert exc.value.status_code == 403
    assert exc.value.details["required"] == "admin"
    assert guard(CurrentUser(username="a", role="admin", via="session")).role == "admin"
