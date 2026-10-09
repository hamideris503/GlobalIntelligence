"""Tests for Ops status API (Phase 49)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_ops_status_shape(client: TestClient) -> None:
    res = client.get("/api/ops/status")
    assert res.status_code == 200
    body = res.json()
    assert body["database_ok"] is True
    assert body["counts"]["sources"] >= 0
    assert isinstance(body["last_jobs"], list)
    assert isinstance(body["latest_self_eval"], dict)
    assert isinstance(body["active_alerts"], int)
    assert isinstance(body["latest_world_state"], dict)


def test_ops_status_requires_key() -> None:
    import os

    from fastapi.testclient import TestClient as TC

    from backend.core.config import get_settings
    from backend.main import app

    os.environ["API_KEY"] = "test-key-123"
    get_settings.cache_clear()
    try:
        res = TC(app, raise_server_exceptions=False).get("/api/ops/status")
        assert res.status_code == 401
    finally:
        os.environ["API_KEY"] = ""
        get_settings.cache_clear()
