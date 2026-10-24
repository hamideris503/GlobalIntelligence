"""Validation hardening for /api/ingest/bot — auth واقعی، قفل، session تزریقی.

همه روی sqlite conftest؛ هیچ اتصال/write به DB واقعی نیست (تست صریح دارد).
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from tests.conftest import TestingSession


def _authed_client() -> TestClient:
    from fastapi.testclient import TestClient as TC

    from backend.main import app

    os.environ["API_KEY"] = "test-key-123"
    get_settings.cache_clear()
    return TC(app, raise_server_exceptions=False)


@pytest.fixture
def authed():
    c = _authed_client()
    try:
        yield c
    finally:
        os.environ["API_KEY"] = ""
        get_settings.cache_clear()


def _mk_source(name="v-src"):
    db = TestingSession()
    db.add(Source(name=name, collection_method="rss", type="rss",
                  feed_url="https://example.test/rss"))
    db.commit()
    db.close()


def test_bot_requires_api_key(authed: TestClient):
    assert authed.post("/api/ingest/bot", json={}).status_code == 401
    assert authed.post("/api/ingest/bot", json={},
                       headers={"X-API-Key": "wrong"}).status_code == 401
    # کلید درست از احراز می‌گذرد (منبع ناموجود -> 404 یعنی auth پاس شد)
    res = authed.post("/api/ingest/bot", json={"source_name": "nope"},
                      headers={"X-API-Key": "test-key-123"})
    assert res.status_code == 404


def test_bot_limit_validation(client: TestClient):
    assert client.post("/api/ingest/bot", json={"limit": 0}).status_code == 422
    assert client.post("/api/ingest/bot", json={"limit": 201}).status_code == 422
    assert client.post("/api/ingest/bot", json={"limit": -5}).status_code == 422


def test_endpoint_never_touches_real_session_factory(client: TestClient, monkeypatch):
    """run_once بدون db صدا زده نمی‌شود؛ factory واقعی production لمس نمی‌شود."""
    import source_bot.runner as runner_module

    _mk_source("v-src2")

    def _boom():
        raise AssertionError("real session factory must not be used in tests")

    async def fake_fetch(plan, settings):
        return ([RawItem(title="T", url="https://example.test/9",
                         raw_text="validation body " * 20)], "", {})

    monkeypatch.setattr(runner_module, "get_session_factory", _boom)
    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    res = client.post("/api/ingest/bot", json={"source_name": "v-src2"})
    assert res.status_code == 200, res.text
    assert res.json()["stored"] == 1


def test_run_uses_injected_sqlite_session(client: TestClient, monkeypatch):
    """session تزریق‌شده دقیقاً همان sqlite تست است (نه postgres)."""
    import source_bot.runner as runner_module

    _mk_source("v-src3")
    seen = {}

    real_run_source = runner_module.run_source

    async def spy(db, source, metrics, settings=None, **kwargs):
        seen["driver"] = db.get_bind().url.drivername
        seen["same_db"] = db.get_bind() is TestingSession.kw["bind"]
        return await real_run_source(db, source, metrics, settings, **kwargs)

    async def fake_fetch(plan, settings):
        return ([RawItem(title="T2", url="https://example.test/10",
                         raw_text="identity body " * 20)], "", {})

    monkeypatch.setattr(runner_module, "run_source", spy)
    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    res = client.post("/api/ingest/bot", json={"source_name": "v-src3"})
    assert res.status_code == 200, res.text
    assert seen["driver"] == "sqlite"
    assert seen["same_db"] is True


def test_lock_released_after_run_once_error():
    """خطا داخل run_once (مثل منبع ناموجود) قفل را آزاد می‌کند (finally) —
    با session تزریقی sqlite؛ بدون تماس با DB واقعی."""
    import asyncio
    import os

    import source_bot.runner as runner_module
    from tests.conftest import TestingSession as TS

    db = TS()
    try:
        with pytest.raises(ValueError):
            asyncio.run(runner_module.run_once(source_name="definitely-missing", db=db))
        assert runner_module._acquire_lock() is True
        runner_module._release_lock()
        assert not os.path.exists(runner_module.LOCK_PATH)
    finally:
        db.close()


def test_source_error_isolated_and_lock_free(client: TestClient, monkeypatch):
    import source_bot.runner as runner_module

    async def failing_fetch(plan, settings):
        raise RuntimeError("boom")

    _mk_source("v-src5")
    monkeypatch.setattr(runner_module, "_fetch_plan", failing_fetch)
    res = client.post("/api/ingest/bot", json={"source_name": "v-src5"})
    # خطای منبع ایزوله می‌شود (failed ثبت، نه 500) و قفل آزاد می‌ماند
    assert res.status_code == 200, res.text
    assert "v-src5" in res.json()["sources_failed"]
    assert runner_module._acquire_lock() is True
    runner_module._release_lock()


def test_keyless_item_never_stored_and_rerun_safe(client: TestClient, monkeypatch):
    """آیتم بدون کلید (نه URL نه متن) هرگز ذخیره نمی‌شود؛ rerun تکراری نمی‌سازد."""
    import source_bot.runner as runner_module
    from backend.database.models.document import Document

    _mk_source("v-keyless")

    async def fake_fetch(plan, settings):
        return ([RawItem(title=None, url=None, raw_text=None)], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    total_duplicates = 0
    for _ in range(2):
        res = client.post("/api/ingest/bot", json={"source_name": "v-keyless"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["stored"] == 0
        total_duplicates += body["duplicates"]
    assert total_duplicates == 2
    db = TestingSession()
    try:
        assert db.query(Document).count() == 0
    finally:
        db.close()
