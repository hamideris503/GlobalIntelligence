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
    # AUDIT-REPAIR: هیچ فیلد محیطی/حساسی فاش نشود
    assert "env" not in body
    assert "secret" not in str(body).lower()


def test_health_liveness() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_db_pool_sized_for_scheduled_bursts(monkeypatch) -> None:
    """E2E: pool باید از پیش‌فرض بزرگ‌تر باشد تا burst ساعتی 500 ندهد."""
    import backend.database.session as sess_mod
    from backend.core.config import get_settings

    assert get_settings().db_pool_size >= 10
    assert get_settings().db_max_overflow >= 20
    captured: dict = {}
    real_create = sess_mod.create_engine

    def fake_create(url, **kwargs):
        captured.update(kwargs)
        return real_create("sqlite://", **{k: v for k, v in kwargs.items()
                                           if k in ("future",)})

    monkeypatch.setattr(sess_mod, "create_engine", fake_create)
    monkeypatch.setattr(sess_mod, "_engine", None)
    try:
        sess_mod.get_engine()
    finally:
        monkeypatch.setattr(sess_mod, "_engine", None)
    assert captured.get("pool_size") == get_settings().db_pool_size
    assert captured.get("max_overflow") == get_settings().db_max_overflow


def test_health_db_shape(monkeypatch) -> None:
    """health/db همیشه 200 برمی‌گرداند اما وضعیت ممکن است ok یا degraded باشد."""
    from backend.api.routers import health as health_router

    monkeypatch.setattr(
        health_router, "check_database", lambda: {"ok": False, "detail": "test"}
    )
    res = client.get("/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert "ok" in body["database"]
