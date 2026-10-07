"""Tests for the FastAPI skeleton (Phase 2).

این تست‌ها به دیتابیس واقعی نیاز ندارند؛ فقط liveness و شکل پاسخ‌ها بررسی می‌شود.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_root() -> None:
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "name" in body


def test_health_liveness() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_db_shape() -> None:
    """health/db همیشه 200 برمی‌گرداند اما وضعیت ممکن است ok یا degraded باشد."""
    res = client.get("/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert "ok" in body["database"]
