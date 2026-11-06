"""قرارداد یکنواخت خطای API (مرحله ۲).

هر خطا `error.code/message/details/request_id` دارد و `detail` قدیمی هم
می‌ماند؛ `X-Request-ID` پذیرفته/تولید و در هدر و لاگ می‌آید.
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, OperationalError

from backend.api import errors
from backend.core.config import get_settings
from backend.core.security import RateLimitMiddleware
from backend.main import app


def _authed(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEY", "test-key-123")
    get_settings.cache_clear()
    return TestClient(app, raise_server_exceptions=False)


def _failing_app() -> TestClient:
    inner = FastAPI()
    inner.add_middleware(errors.RequestIDMiddleware)
    errors.install_error_handlers(inner)

    @inner.get("/boom")
    def boom() -> dict:
        raise RuntimeError("secret internal detail")

    @inner.get("/db")
    def db_down() -> dict:
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2"))

    return TestClient(inner, raise_server_exceptions=False)


def test_handlers_are_installed_on_the_real_app() -> None:
    assert app.exception_handlers[Exception] is errors.internal_error_handler
    assert app.exception_handlers[DBAPIError] is errors.db_error_handler
    assert app.exception_handlers[errors.RequestValidationError] is (
        errors.validation_exception_handler
    )


def test_401_has_envelope_and_detail(client, monkeypatch) -> None:
    res = _authed(monkeypatch).get("/api/sources")
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["detail"] == body["error"]["message"] and body["detail"]
    assert body["error"]["request_id"] == res.headers["X-Request-ID"]
    assert len(body["error"]["request_id"]) == 32  # تولیدشده


def test_invalid_api_key_has_its_own_code(client, monkeypatch) -> None:
    res = _authed(monkeypatch).get("/api/sources", headers={"X-API-Key": "wrong"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_API_KEY"


def test_request_id_is_echoed_when_valid(client) -> None:
    res = client.get("/health", headers={"X-Request-ID": "req-abc.123"})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "req-abc.123"


def test_request_id_is_replaced_when_malformed(client) -> None:
    res = client.get("/health", headers={"X-Request-ID": "<script>alert(1)</script>"})
    assert res.status_code == 200
    value = res.headers["X-Request-ID"]
    assert value != "<script>alert(1)</script>" and len(value) == 32


def test_404_envelope(client) -> None:
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["detail"] == body["error"]["message"]


def test_405_envelope_is_not_swallowed_by_static(client) -> None:
    """StaticFiles روی `/` نباید 405 واقعی را به 404 تبدیل کند."""
    res = client.get("/api/ingest/all")
    assert res.status_code == 405
    assert res.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_validation_error_carries_fields_and_legacy_detail(client) -> None:
    res = client.post("/api/sources", json={"type": "nope"})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "name" in body["error"]["details"]["fields"]
    assert isinstance(body["detail"], list)  # شکل قبلی FastAPI حفظ شده


def test_500_does_not_leak_internals() -> None:
    res = _failing_app().get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["error"]["code"] == "INTERNAL"
    assert "secret internal detail" not in res.text
    assert "Traceback" not in res.text
    assert body["detail"] == body["error"]["message"]
    assert res.headers["X-Request-ID"]


def test_db_error_is_503_without_leaking_credentials() -> None:
    res = _failing_app().get("/db")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DB_UNAVAILABLE"
    assert "hunter2" not in res.text


def test_rate_limit_body_has_envelope_and_retry_after() -> None:
    inner = FastAPI()

    @inner.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    inner.add_middleware(RateLimitMiddleware, per_minute=1)
    inner.add_middleware(errors.RequestIDMiddleware)
    client = TestClient(inner)
    assert client.get("/ping").status_code == 200
    limited = client.get("/ping")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    body = limited.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["request_id"] == limited.headers["X-Request-ID"]
    assert body["detail"] == body["error"]["message"]


def test_ai_error_body_also_has_envelope() -> None:
    from backend.ai.schemas.types import AIError, AIErrorKind

    body = json.loads(
        errors.ai_error_response(AIError("raw", kind=AIErrorKind.rate_limit)).body
    )
    assert body["error"]["code"] == "AI_RATE_LIMIT"
    assert body["error"]["message"] == body["detail"]
    assert body["error"]["details"]["kind"] == "rate_limit"
