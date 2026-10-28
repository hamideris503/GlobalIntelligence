"""Preflight پیکربندی اولویت: توقف پیش از fetch و پیش از ذخیره.

بدون شبکه/AI/DB واقعی: `_fetch_plan` و fetcher ساختگی‌اند و env با monkeypatch
مدیریت می‌شود (هیچ تغییری در محیط دائمی کاربر).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.database import models as _models
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline
from source_bot import jobs as jobs_module
from source_bot.config import BotConfigError
from source_bot.priority_engine import LEVELS
from tests.conftest import TestingSession

# هر حالت نامعتبر: غیرعددی، خارج از محدوده، ترتیب وارون، تساوی مرزها
BAD_ENVS = [
    {"SOURCE_BOT_TH_P0": "abc"},
    {"SOURCE_BOT_TH_P0": "150"},
    {"SOURCE_BOT_TH_P3": "-5"},
    {"SOURCE_BOT_TH_P0": "50", "SOURCE_BOT_TH_P1": "75"},
    {"SOURCE_BOT_TH_P0": "90", "SOURCE_BOT_TH_P1": "90"},
]


def _mk_source(name: str = "pf-src") -> None:
    db = TestingSession()
    try:
        db.add(Source(name=name, collection_method="rss", type="rss",
                      feed_url="https://pf.test/rss"))
        db.commit()
    finally:
        db.close()


def _docs() -> list:
    db = TestingSession()
    try:
        return db.query(_models.Document).all()
    finally:
        db.close()


def _wire(monkeypatch, calls: list) -> None:
    """محیط ایزوله: transport ساختگی، بدون retry/sleep/AI، session آزمایشی."""
    from source_bot import runner as runner_module

    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: TestingSession)

    async def _fake(plan, settings):
        calls.append(plan.url)
        return ([RawItem(title="Triage dispatch", url=f"{plan.url}/1",
                         raw_text="ward logistics update " * 20,
                         raw_payload='{"title": "Triage dispatch"}')], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", _fake)


def _set_env(monkeypatch, env: dict) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


class _SpyFetcher:
    """fetcher ساختگی مسیر عادی ingestion: فقط تماس را ثبت می‌کند."""

    def __init__(self, calls: list) -> None:
        self.calls = calls

    async def fetch(self, *, url=None, limit: int = 20):
        self.calls.append(url)
        return [RawItem(title="Triage dispatch", url="https://pf.test/1",
                        raw_text="ward logistics update " * 20)]


# --- اجرای معتبر: رفتار فعلی دست‌نخورده ---

def test_valid_config_runs_normally(client: TestClient, monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)

    res = client.post("/api/ingest/bot", json={"source_name": "pf-src", "limit": 5})
    assert res.status_code == 200, res.text
    assert calls == ["https://pf.test/rss"]

    doc = _docs()[0]
    assert doc.ingestion_priority in LEVELS
    assert doc.priority_source == "rules"
    # provenance دست‌نخورده: منبع تصمیم در metadata ثبت شده است
    assert "priority_decision_source" in (doc.doc_metadata or "")


def test_plain_ingest_runs_normally_with_valid_config(monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)

    db = TestingSession()
    try:
        src = db.query(Source).filter(Source.name == "pf-src").one()
        pipe = NewsIngestionPipeline(db, fetcher=_SpyFetcher(calls))
        result = asyncio.run(pipe.ingest_source_async(src, limit=5))
    finally:
        db.close()

    assert calls == ["https://pf.test/rss"] and result.stored == 1 and result.errors == []
    assert _docs()[0].ingestion_priority in LEVELS


# --- پیکربندی نامعتبر: توقف پیش از fetch و پیش از ذخیره ---

@pytest.mark.parametrize("env", BAD_ENVS)
def test_bot_endpoint_returns_clear_error_before_fetch(env, client: TestClient,
                                                       monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    _set_env(monkeypatch, env)

    res = client.post("/api/ingest/bot", json={"source_name": "pf-src", "limit": 5})
    assert res.status_code == 500  # خطای پیکربندی سرور، نه 404 «درخواست نامعتبر»
    assert "priority configuration invalid" in res.json()["detail"]
    assert calls == []          # هیچ fetch انجام نشد
    assert _docs() == []        # هیچ ذخیره‌ای انجام نشد


@pytest.mark.parametrize("env", BAD_ENVS)
def test_run_once_stops_before_fetch(env, monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    _set_env(monkeypatch, env)

    from source_bot.runner import run_once

    with pytest.raises(BotConfigError):
        asyncio.run(run_once(source_name="pf-src", limit_sources=5))
    assert calls == [] and _docs() == []


@pytest.mark.parametrize("env", BAD_ENVS)
def test_run_source_validates_before_fetch(env, monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    _set_env(monkeypatch, env)

    from source_bot.runner import BotMetrics, run_source

    db = TestingSession()
    try:
        src = db.query(Source).filter(Source.name == "pf-src").one()
        with pytest.raises(BotConfigError):
            asyncio.run(run_source(db, src, BotMetrics()))  # settings=None -> خودش می‌سازد
    finally:
        db.close()
    assert calls == [] and _docs() == []


@pytest.mark.parametrize("env", BAD_ENVS)
def test_plain_ingest_stops_before_fetch(env, monkeypatch) -> None:
    """مسیر عادی ingestion: پیش‌تر خطا در `store_item` گرفته می‌شد و سند NULL می‌شد."""
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    _set_env(monkeypatch, env)

    db = TestingSession()
    try:
        src = db.query(Source).filter(Source.name == "pf-src").one()
        pipe = NewsIngestionPipeline(db, fetcher=_SpyFetcher(calls))
        result = asyncio.run(pipe.ingest_source_async(src, limit=5))
        assert db.query(_models.Document).count() == 0
    finally:
        db.close()

    assert calls == []
    assert result.stored == 0 and result.duplicates == 0
    assert any("priority configuration invalid" in e for e in result.errors)


@pytest.mark.parametrize("env", BAD_ENVS)
def test_job_fails_with_clear_message_before_fetch(env, client: TestClient,
                                                   monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    _set_env(monkeypatch, env)

    res = client.post("/api/ingest/jobs", json={"source_name": "pf-src"})
    assert res.status_code == 202, res.text
    body = client.get(f"/api/ingest/jobs/{res.json()['id']}").json()

    assert body["status"] == "failed"       # قرارداد موجود Job، بدون schema جدید
    assert "priority configuration invalid" in (body["message"] or "")
    assert body["result"] is None or body["result"].get("stored") in (None, 0)
    assert calls == [] and _docs() == []


# --- خطای پیکربندی، کل اپ را متوقف نمی‌کند ---

def test_app_stays_healthy_after_config_error(client: TestClient, monkeypatch) -> None:
    _mk_source()
    calls: list = []
    _wire(monkeypatch, calls)
    monkeypatch.setenv("SOURCE_BOT_TH_P0", "abc")

    assert client.post("/api/ingest/bot", json={"source_name": "pf-src"}).status_code == 500
    assert client.get("/health").status_code == 200

    # و پس از رفع پیکربندی، همان اپ اجرای سالم انجام می‌دهد (بدون restart)
    monkeypatch.delenv("SOURCE_BOT_TH_P0")
    res = client.post("/api/ingest/bot", json={"source_name": "pf-src"})
    assert res.status_code == 200, res.text
    assert calls == ["https://pf.test/rss"]
