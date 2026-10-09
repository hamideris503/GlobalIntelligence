"""Tests for Security Hardening (Phase 44).

- همه‌ی routerهای API بدون کلید 401 می‌دهند؛ health عمومی است.
- هدرهای امنیتی روی پاسخ‌ها (از جمله 429) می‌نشینند.
- محدودیت نرخ با حد پایین قابل آزمون است.
- production ناامن fail-fast می‌شود (DEBUG هم بررسی می‌شود).
"""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.security import RateLimitMiddleware, SecurityHeadersMiddleware


def _authed_client() -> TestClient:
    """کلاینت با احراز هویت فعال (conftest آن را غیرفعال می‌کند)."""
    import os

    from fastapi.testclient import TestClient as TC

    from backend.core.config import get_settings
    from backend.main import app

    os.environ["API_KEY"] = "test-key-123"
    get_settings.cache_clear()
    return TC(app, raise_server_exceptions=False)


def test_protected_routes_require_key(client: TestClient) -> None:
    authed = _authed_client()
    try:
        paths = [
        "/api/sources",
        "/api/ingest/all",
        "/api/dedup/run",
        "/api/classify/run",
        "/api/events",
        "/api/claims",
        "/api/graph/entities",
        "/api/economic/indicators",
        "/api/markets/symbols",
        "/api/world-state/history",
        "/api/memory/stats",
        "/api/analogues",
        "/api/macro/assessments",
        "/api/geopolitics/assessments",
        "/api/society/mood",
        "/api/narratives",
        "/api/forecasts",
        "/api/outcomes/pending",
        "/api/evaluation/summary",
        "/api/tournaments",
        "/api/scenarios",
        "/api/risk/overview",
        "/api/decisions",
        "/api/iran/brief",
        "/api/portfolios",
        "/api/performance",
        "/api/ai-routing/stats",
        "/api/audit/records",
        "/api/self-eval/history",
        "/api/briefings",
        "/api/alerts",
    ]
        for path in paths:
            res = authed.get(path)
            assert res.status_code in (401, 403, 405), f"{path} -> {res.status_code}"
    finally:
        import os

        from backend.core.config import get_settings

        os.environ["API_KEY"] = ""
        get_settings.cache_clear()


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_security_headers_present(client: TestClient) -> None:
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in res.headers


def test_rate_limit_429() -> None:
    inner = FastAPI()

    @inner.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    inner.add_middleware(RateLimitMiddleware, per_minute=2)
    inner.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(inner)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    limited = client.get("/ping")
    assert limited.status_code == 429
    assert limited.headers["X-Content-Type-Options"] == "nosniff"


def test_rate_limit_exempts_health() -> None:
    inner = FastAPI()

    @inner.get("/health")
    def health() -> dict:
        return {"ok": True}

    inner.add_middleware(RateLimitMiddleware, per_minute=1)
    client = TestClient(inner)
    for _ in range(3):
        assert client.get("/health").status_code == 200


def test_production_validation() -> None:
    from backend.core.config import get_settings

    old = dict(os.environ)
    try:
        os.environ.update(
            {
                "APP_ENV": "production",
                "API_KEY": "k",
                "SECRET_KEY": "s3cret!",
                "MOCK_MODE": "false",
                "DEBUG": "true",  # ناامن
            }
        )
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="DEBUG"):
            get_settings().validate_production()
        os.environ["DEBUG"] = "false"
        get_settings.cache_clear()
        get_settings().validate_production()  # بدون خطا
    finally:
        os.environ.clear()
        os.environ.update(old)
        get_settings.cache_clear()


def test_production_hides_docs() -> None:
    from backend.main import create_app

    old = dict(os.environ)
    try:
        os.environ.update(
            {
                "APP_ENV": "production",
                "API_KEY": "k",
                "SECRET_KEY": "s3cret!",
                "MOCK_MODE": "false",
                "DEBUG": "false",
            }
        )
        from backend.core.config import get_settings as gs

        gs.cache_clear()
        prod_app = create_app()
        paths = {getattr(r, "path", "") for r in prod_app.routes}
        assert "/docs" not in paths
        assert "/openapi.json" not in paths
    finally:
        os.environ.clear()
        os.environ.update(old)
        gs.cache_clear()
