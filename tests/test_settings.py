"""Tests for Settings panel backend (Step 8-A).

Secrets in tests are obviously-fake values (repo convention, e.g. test-key-123).
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from fastapi.testclient import TestClient as TC

from backend.ai import credentials_store as store
from backend.ai.credentials import (
    CredentialError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
    validate_base_url,
)
from backend.core.config import get_settings
from backend.database.models.ai_settings import (
    AgentAssignment,
    AIModelRow,
    AIProviderRow,
)
from backend.main import app
from tests.conftest import TestingSession

FAKE_KEY = "test-fake-key-abcdef123456"


@pytest.fixture(autouse=True)
def _enc_key():
    os.environ["APP_ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    get_settings.cache_clear()
    store.set_session_factory(TestingSession)
    try:
        yield
    finally:
        os.environ.pop("APP_ENCRYPTION_KEY", None)
        get_settings.cache_clear()
        store.set_session_factory(None)


def _provider(session, name="P1", kind="groq", key=FAKE_KEY):
    p = AIProviderRow(name=name, kind=kind, enabled=True)
    session.add(p)
    session.flush()
    if key is not None:
        p.api_key_encrypted = encrypt_secret(key)
        p.key_hint = mask_secret(True, key[-4:])
    session.commit()
    return p


# --- crypto ---
def test_encrypt_roundtrip_and_refuse_without_key(monkeypatch) -> None:
    assert decrypt_secret(encrypt_secret(FAKE_KEY)) == FAKE_KEY
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(CredentialError):
            encrypt_secret(FAKE_KEY)
    finally:
        get_settings.cache_clear()


def test_mask() -> None:
    assert mask_secret(False) == "not set"
    assert mask_secret(True, "1234") == "••••1234"


# --- SSRF ---
def test_base_url_https_required() -> None:
    with pytest.raises(CredentialError):
        validate_base_url("http://example.com/api")


def test_base_url_private_blocked() -> None:
    for bad in ("https://localhost:8000/x", "https://127.0.0.1/", "https://10.0.0.5/",
                "https://192.168.1.1/", "https://internal.local/"):
        with pytest.raises(CredentialError):
            validate_base_url(bad)


def test_base_url_public_ok() -> None:
    assert validate_base_url("https://api.example.com/v1/") == "https://api.example.com/v1"


# --- providers CRUD: no secret leaks ---
def test_provider_create_never_returns_key(client: TestClient) -> None:
    res = client.post("/api/settings/providers",
                      json={"name": "G1", "kind": "groq", "api_key": FAKE_KEY})
    assert res.status_code == 200
    body = res.json()
    assert body["key_set"] is True
    assert body["key_hint"] == "••••3456"
    raw = json.dumps(body)
    assert FAKE_KEY not in raw
    assert "api_key" not in body


def test_provider_create_refuses_without_encryption_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    res = client.post("/api/settings/providers",
                      json={"name": "G2", "kind": "groq", "api_key": FAKE_KEY})
    assert res.status_code == 422


def test_no_secret_in_logs_or_outputs(client: TestClient, caplog) -> None:
    import logging

    with caplog.at_level(logging.INFO):
        res = client.post("/api/settings/providers",
                          json={"name": "GL", "kind": "groq", "api_key": FAKE_KEY})
        assert res.status_code == 200
        pid = res.json()["id"]
        client.post(f"/api/settings/providers/{pid}/key",
                    json={"api_key": "test-fake-key-QQQQ7777"})
        client.get("/api/settings/providers")
    assert FAKE_KEY not in caplog.text
    assert "QQQQ7777" not in caplog.text


def test_key_rotate_and_list_masked(client: TestClient) -> None:
    session = TestingSession()
    try:
        p = _provider(session)
        pid = str(p.id)
    finally:
        session.close()
    res = client.post(f"/api/settings/providers/{pid}/key",
                      json={"api_key": "test-fake-key-ZZZZ9999"})
    assert res.status_code == 200
    assert res.json()["key_hint"] == "••••9999"
    listing = client.get("/api/settings/providers").json()
    assert all("api_key" not in item for item in listing)
    assert FAKE_KEY not in json.dumps(listing)


def test_delete_blocked_when_assigned(client: TestClient) -> None:
    session = TestingSession()
    try:
        p = _provider(session)
        pid = str(p.id)
        m = AIModelRow(provider_id=p.id, model_name="m1", enabled=True)
        session.add(m)
        session.flush()
        session.add(AgentAssignment(agent="bull", provider_id=p.id,
                                    model_id=m.id, enabled=True))
        session.commit()
    finally:
        session.close()
    res = client.delete(f"/api/settings/providers/{pid}")
    assert res.status_code == 409
    assert "bull" in res.json()["detail"]


def test_delete_ok_when_unused(client: TestClient) -> None:
    session = TestingSession()
    try:
        pid = str(_provider(session).id)
    finally:
        session.close()
    assert client.delete(f"/api/settings/providers/{pid}").status_code == 200


def test_settings_requires_key() -> None:
    os.environ["API_KEY"] = "test-key-123"
    get_settings.cache_clear()
    try:
        res = TC(app, raise_server_exceptions=False).get("/api/settings/providers")
        assert res.status_code == 401
    finally:
        os.environ["API_KEY"] = ""
        get_settings.cache_clear()


# --- models/prices/diversity ---
def test_models_crud_and_diversity(client: TestClient) -> None:
    session = TestingSession()
    try:
        p = _provider(session)
        pid = str(p.id)
    finally:
        session.close()
    res = client.post("/api/settings/models",
                      json={"provider_id": pid, "model_name": "m1",
                            "price_in_per_mtok": 1.0, "price_out_per_mtok": 2.0})
    assert res.status_code == 200
    mid = res.json()["id"]
    res = client.put("/api/settings/agent-assignments",
                     json=[{"agent": "bull", "provider_id": pid, "model_id": mid},
                           {"agent": "bear", "provider_id": pid, "model_id": mid}])
    assert res.status_code == 200
    div = client.get("/api/settings/diversity").json()
    assert div["distinct_models"] == 1
    assert div["warning"] is not None  # تنوع ۱ هشدار دارد


def test_model_delete_blocked_when_assigned(client: TestClient) -> None:
    session = TestingSession()
    try:
        p = _provider(session)
        m = AIModelRow(provider_id=p.id, model_name="m1", enabled=True)
        session.add(m)
        session.flush()
        mid = str(m.id)
        session.add(AgentAssignment(agent="bear", provider_id=p.id,
                                    model_id=m.id, enabled=True))
        session.commit()
    finally:
        session.close()
    res = client.delete(f"/api/settings/models/{mid}")
    assert res.status_code == 409


# --- app settings ---
def test_app_settings_allowlist_and_secret_refusal(client: TestClient) -> None:
    res = client.put("/api/settings/app",
                     json={"settings": {"debate_daily_budget_usd": "7.5"}})
    assert res.status_code == 200
    assert client.get("/api/settings/app").json()["debate_daily_budget_usd"] == "7.5"
    bad = client.put("/api/settings/app", json={"settings": {"nope": "1"}})
    assert bad.status_code == 422
    from backend.ai.credentials_store import set_app_setting

    session = TestingSession()
    try:
        with pytest.raises(CredentialError):
            set_app_setting(session, "MY_API_KEY", "x")
    finally:
        session.close()


# --- import from env ---
def test_import_from_env_needs_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    res = client.post("/api/settings/import-from-env")
    assert res.status_code == 200
    assert res.json()["needs_encryption_key"] is True
    assert res.json()["moved"] == []


# --- gateway: fallback + reload ---
def test_gateway_falls_back_to_env_without_rows(monkeypatch) -> None:
    from backend.ai.providers.registry import build_provider_with_store

    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    try:
        prov = build_provider_with_store("groq")
        assert prov.name == "groq"
        assert not prov.configured()  # نه DB نه .env (تست)
    finally:
        get_settings.cache_clear()


def test_gateway_uses_db_row_and_reloads() -> None:
    from backend.ai.gateway import AIGateway
    from backend.ai.providers.registry import build_provider_with_store

    session = TestingSession()
    try:
        _provider(session, name="GRQ", kind="groq")
    finally:
        session.close()
    prov = build_provider_with_store("groq")
    assert prov.configured()
    assert prov.api_key == FAKE_KEY
    gw = AIGateway()
    v0 = gw._cred_version
    store.bump_version()
    gw._provider("groq")  # کش باید باطل شده باشد
    assert gw._cred_version != v0


# --- debate price gate + void ---
def test_debate_price_missing() -> None:
    import asyncio

    from domains.debate.engine import DebateEngine
    from tests.test_debate import _seed_prices

    session = TestingSession()
    try:
        _seed_prices(session)
        engine = DebateEngine(session)
        out = asyncio.run(engine.run(target="market:WTI", horizon_days=30))
        assert out.status == "price_missing"
        assert out.run_id is not None
    finally:
        session.close()


def test_void_endpoints(client: TestClient) -> None:
    from backend.database.models.debate import DebateRun
    from backend.database.models.forecast import Forecast

    session = TestingSession()
    try:
        run = DebateRun(target="market:WTI", status="done")
        session.add(run)
        fc = Forecast(target="market:WTI", status="active")
        session.add(fc)
        session.commit()
        rid, fid = str(run.id), str(fc.id)
    finally:
        session.close()
    assert client.post(f"/api/settings/debate-runs/{rid}/void",
                       json={"reason": "bad context"}).status_code == 200
    assert client.post(f"/api/settings/forecasts/{fid}/void",
                       json={"reason": "stale"}).status_code == 200
    session = TestingSession()
    try:
        import uuid as _uuid

        assert session.get(DebateRun, _uuid.UUID(rid)).status == "void"
        assert session.get(Forecast, _uuid.UUID(fid)).status == "void"
    finally:
        session.close()


def test_login_ok_and_fail(client: TestClient) -> None:
    import os as _os

    _os.environ["ADMIN_USERNAME"] = "admin"
    _os.environ["ADMIN_PASSWORD"] = "admin"
    get_settings.cache_clear()
    try:
        bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert bad.status_code == 401
        ok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert ok.status_code == 200
        assert ok.json()["ok"] is True
        assert "password" not in ok.json()
    finally:
        _os.environ.pop("ADMIN_USERNAME", None)
        _os.environ.pop("ADMIN_PASSWORD", None)
        get_settings.cache_clear()


def test_env_providers_listed_readonly(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-env-key-1234567890")
    get_settings.cache_clear()
    try:
        items = client.get("/api/settings/providers").json()
        env_rows = [i for i in items if i["key_source"] == "env"]
        assert any(i["kind"] == "gemini" and i["id"] == "env:gemini" for i in env_rows)
        assert all("api_key" not in i for i in items)
        # حذف/ویرایش ردیف env مسدود است
        bad = client.delete("/api/settings/providers/env:gemini")
        assert bad.status_code == 422
    finally:
        get_settings.cache_clear()


def test_model_on_env_provider_creates_shell(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-fake-env-key-1234567890")
    get_settings.cache_clear()
    try:
        res = client.post("/api/settings/models",
                          json={"provider_id": "env:groq", "model_name": "m-env",
                                "price_in_per_mtok": 0.5, "price_out_per_mtok": 1.0})
        assert res.status_code == 200
        items = client.get("/api/settings/providers").json()
        assert any(i["kind"] == "groq" and i["key_source"] == "db" for i in items)
    finally:
        get_settings.cache_clear()


def test_env_provider_test_wires_without_network(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-fake-env-key-1234567890")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()
    try:
        res = client.post("/api/settings/providers/env:groq/test", json={})
        assert res.status_code == 200
        assert res.json()["provider"] == "groq"  # بدون تماس واقعی (mock)
    finally:
        get_settings.cache_clear()


def test_provider_create_with_default_model(client: TestClient) -> None:
    """مدل پیش‌فرض همان فرم افزودن ساخته می‌شود (بدون قیمت؛ بعداً ثبت می‌شود)."""
    res = client.post("/api/settings/providers",
                      json={"name": "GDM", "kind": "groq", "api_key": FAKE_KEY,
                            "default_model": "llama-3.3-70b-versatile"})
    assert res.status_code == 200
    models = client.get("/api/settings/models").json()
    mine = [m for m in models if m["provider_name"] == "GDM"]
    assert len(mine) == 1
    assert mine[0]["model_name"] == "llama-3.3-70b-versatile"
    assert mine[0]["price_in_per_mtok"] is None


def test_mock_mode_override_from_panel(client: TestClient) -> None:
    """override حالت اجرا از پنل؛ بدون ری‌استارت؛ اعتبارسنجی ورودی."""
    from backend.ai import credentials_store as store

    # پیش‌فرض تست: mock (از .env)
    assert store.effective_mock_mode() is True
    res = client.put("/api/settings/app", json={"settings": {"mock_mode": "false"}})
    assert res.status_code == 200
    assert store.effective_mock_mode() is False
    status = client.get("/api/ai/status").json()
    assert status["mock_mode"] is False
    # برگرداندن
    back = client.put("/api/settings/app", json={"settings": {"mock_mode": "true"}})
    assert back.status_code == 200
    assert store.effective_mock_mode() is True
    # ورودی نامعتبر
    bad = client.put("/api/settings/app", json={"settings": {"mock_mode": "maybe"}})
    assert bad.status_code == 422


def test_default_provider_override(client: TestClient) -> None:
    from backend.ai import credentials_store as store

    res = client.put("/api/settings/app",
                     json={"settings": {"ai_default_provider": "groq"}})
    assert res.status_code == 200
    assert store.effective_default_provider() == "groq"
    assert client.get("/api/ai/status").json()["default_provider"] == "groq"
    bad = client.put("/api/settings/app", json={"settings": {"ai_default_provider": " "}})
    assert bad.status_code == 422


def test_import_moves_cloudflare_account_id(client: TestClient, monkeypatch) -> None:
    """Step 9: import-from-env باید Account ID کلادفلر را هم منتقل کند."""
    import json as _json

    from sqlalchemy import select as _select

    from backend.database.models.ai_settings import AIProviderRow

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-fake-cf-token-1234567890")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-fake-acct-1234")
    get_settings.cache_clear()
    try:
        res = client.post("/api/settings/import-from-env")
        assert res.status_code == 200
        assert "cloudflare" in res.json()["moved"]
        session = TestingSession()
        try:
            row = session.execute(
                _select(AIProviderRow).where(AIProviderRow.kind == "cloudflare")
            ).scalars().first()
            assert row is not None
            from backend.ai.credentials import decrypt_secret

            extra = _json.loads(decrypt_secret(row.extra_encrypted))
            assert extra["account_id"] == "test-fake-acct-1234"
            assert "test-fake-cf-token" not in _json.dumps(res.json())
        finally:
            session.close()
    finally:
        get_settings.cache_clear()


def test_app_settings_update_is_audited(client: TestClient) -> None:
    """تغییر تنظیمات عمومی هم در audit ثبت می‌شود (مثل بقیه‌ی تغییرات)."""
    from sqlalchemy import select as _select

    from backend.database.models.audit_record import AuditRecord

    res = client.put("/api/settings/app",
                     json={"settings": {"debate_max_rounds": "3"}})
    assert res.status_code == 200
    session = TestingSession()
    try:
        rows = session.execute(
            _select(AuditRecord).where(AuditRecord.action == "app_settings_update")
        ).scalars().all()
        assert len(rows) == 1
        assert "debate_max_rounds" in (rows[0].params or "")
    finally:
        session.close()
