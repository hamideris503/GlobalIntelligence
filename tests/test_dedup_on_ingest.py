"""اتصال dedup پس از ingest به مسیر Source Bot (مرحله اصلاح ۱).

SQLite ایزوله، adapter ساختگی و DedupService واقعی؛ هیچ شبکه/دیتابیس واقعی/AI زنده.
قرارداد تست‌شده: dedup خودکار حداکثر یک بار به‌ازای هر اجرای دریافت و فقط وقتی
`dedup_on_ingest` روشن است و سندی تازه ذخیره شده باشد.
"""
from __future__ import annotations

import asyncio
import json

from backend.core.config import get_settings
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.dedup_service import DedupService
from domains.news.fetchers import RawItem
from domains.news.ingestion import IngestionResult, NewsIngestionPipeline
from source_bot import runner as runner_module
from tests.conftest import TestingSession

BODY = "identical ward logistics dispatch body " * 8


def _mk_source(name: str, feed: str) -> None:
    db = TestingSession()
    try:
        db.add(Source(name=name, collection_method="rss", type="rss", feed_url=feed))
        db.commit()
    finally:
        db.close()


def _fetch(per_source: dict[str, list[str]]):
    """transport ساختگی: برای هر feed_url فهرست URL آیتم‌ها با بدنه‌ی یکسان."""
    async def _fake(plan, settings):
        items = [
            RawItem(title="Same dispatch", url=u, raw_text=BODY,
                    raw_payload=json.dumps({"title": "Same dispatch"}))
            for u in per_source.get(plan.url or "", [])
        ]
        return items, "", {}
    return _fake


def _wire(monkeypatch, fetch, *, dedup: bool) -> list[dict]:
    """محیط ایزوله: بدون شبکه/retry/sleep، session آزمایشی، شمارنده‌ی فراخوانی dedup."""
    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
    monkeypatch.setenv("DEDUP_ON_INGEST", "true" if dedup else "false")
    monkeypatch.setattr(runner_module, "_fetch_plan", fetch)
    monkeypatch.setattr(runner_module, "get_session_factory", lambda: TestingSession)
    calls: list[dict] = []
    real_run = DedupService.run

    def spy(self, **kwargs):
        calls.append(kwargs)
        return real_run(self, **kwargs)

    monkeypatch.setattr(DedupService, "run", spy)
    return calls


def _doc_rows() -> list[tuple]:
    db = TestingSession()
    try:
        return [
            (d.source_id, d.url, d.raw_text, d.content_hash, d.doc_metadata)
            for d in db.query(Document).all()
        ]
    finally:
        db.close()


def _clusters() -> list[str | None]:
    return [json.loads(meta or "{}").get("dedup_cluster") for *_r, meta in _doc_rows()]


def test_bot_run_clusters_similar_documents_and_calls_dedup_once(monkeypatch) -> None:
    """دو سند مشابه با URL متفاوت از دو منبع واقعی runner → یک خوشه، بدون فراخوانی دستی."""
    _mk_source("s1", "https://one.test/rss")
    _mk_source("s2", "https://two.test/rss")
    calls = _wire(monkeypatch, _fetch({
        "https://one.test/rss": ["https://one.test/a"],
        "https://two.test/rss": ["https://two.test/b"],
    }), dedup=True)

    metrics = asyncio.run(runner_module.run_once(limit_sources=10))

    assert metrics.stored == 2
    assert len(calls) == 1  # یک بار به‌ازای اجرا، نه هر منبع
    clusters = _clusters()
    assert len(clusters) == 2 and len(set(clusters)) == 1 and clusters[0] is not None


def test_dedup_runs_once_no_matter_how_many_sources_or_items(monkeypatch) -> None:
    feeds = {f"https://s{i}.test/rss": [f"https://s{i}.test/a", f"https://s{i}.test/b"]
             for i in (1, 2, 3)}
    for i in (1, 2, 3):
        _mk_source(f"s{i}", f"https://s{i}.test/rss")
    calls = _wire(monkeypatch, _fetch(feeds), dedup=True)

    metrics = asyncio.run(runner_module.run_once(limit_sources=10))

    assert metrics.stored == 6
    assert len(calls) == 1  # ۳ منبع × ۲ آیتم ⇒ هنوز یک فراخوانی


def test_dedup_disabled_on_ingest_does_not_run(monkeypatch) -> None:
    _mk_source("s1", "https://one.test/rss")
    calls = _wire(monkeypatch, _fetch({"https://one.test/rss": ["https://one.test/a"]}),
                  dedup=False)

    metrics = asyncio.run(runner_module.run_once(limit_sources=10))

    assert metrics.stored == 1
    assert calls == []
    assert _clusters() == [None]  # سند ذخیره شد ولی خوشه‌بندی خودکار اجرا نشد


def test_no_new_document_means_no_dedup_call(monkeypatch) -> None:
    _mk_source("s1", "https://one.test/rss")
    calls = _wire(monkeypatch, _fetch({"https://one.test/rss": []}), dedup=True)

    metrics = asyncio.run(runner_module.run_once(limit_sources=10))

    assert metrics.stored == 0
    assert calls == []


def test_selective_source_run_still_dedups_once(monkeypatch) -> None:
    _mk_source("s1", "https://one.test/rss")
    _mk_source("s2", "https://two.test/rss")
    calls = _wire(monkeypatch, _fetch({
        "https://one.test/rss": ["https://one.test/a"],
        "https://two.test/rss": ["https://two.test/b"],
    }), dedup=True)

    metrics = asyncio.run(runner_module.run_once(source_name="s1", limit_sources=10))

    rows = _doc_rows()
    assert metrics.stored == 1 and len(calls) == 1
    assert [r[1] for r in rows] == ["https://one.test/a"]  # فقط منبع انتخابی


def test_rerun_stores_nothing_new_and_skips_dedup(monkeypatch) -> None:
    _mk_source("s1", "https://one.test/rss")
    calls = _wire(monkeypatch, _fetch({"https://one.test/rss": ["https://one.test/a"]}),
                  dedup=True)

    first = asyncio.run(runner_module.run_once(source_name="s1", limit_sources=10))
    second = asyncio.run(runner_module.run_once(source_name="s1", limit_sources=10))

    assert (first.stored, first.duplicates) == (1, 0)
    assert (second.stored, second.duplicates) == (0, 1)  # تکرار شناسایی شد، حذف نشد
    assert len(calls) == 1  # سند تازه‌ای نبود ⇒ dedup دوباره اجرا نشد
    assert len(_doc_rows()) == 1


def test_dedup_failure_keeps_raw_documents_and_session_usable(monkeypatch) -> None:
    _mk_source("s1", "https://one.test/rss")
    _mk_source("s2", "https://two.test/rss")
    calls = _wire(monkeypatch, _fetch({
        "https://one.test/rss": ["https://one.test/a"],
        "https://two.test/rss": ["https://two.test/b"],
    }), dedup=True)

    def boom(self, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("cluster exploded")

    monkeypatch.setattr(DedupService, "run", boom)

    db = TestingSession()
    try:
        metrics = asyncio.run(runner_module.run_once(limit_sources=10, db=db))
        db.commit()  # session پس از خطای dedup قابل‌استفاده است (rollback در helper)
        rows = [(d.source_id, d.url, d.raw_text, d.content_hash, d.doc_metadata)
                for d in db.query(Document).all()]
    finally:
        db.close()

    assert metrics.stored == 2 and len(calls) == 1  # استثنا به بیرون نشت نکرد
    assert len(rows) == 2  # اسناد خام حذف/rollback نشدند
    for source_id, url, raw_text, content_hash, meta_raw in rows:
        assert source_id is not None and url and raw_text and content_hash
        meta = json.loads(meta_raw or "{}")
        assert meta.get("dedup_cluster") is None  # خوشه‌بندی ناتمام ثبت نشد
        assert meta.get("ingestion_priority")  # provenance دست‌نخورده
        assert meta.get("duplicate_status") == "new"


# --- مسیر A (pipeline) با همان hook مشترک ---
def test_pipeline_path_runs_the_shared_hook_once(monkeypatch) -> None:
    monkeypatch.setenv("DEDUP_ON_INGEST", "true")
    calls: list[dict] = []
    real_run = DedupService.run

    def spy(self, **kwargs):
        calls.append(kwargs)
        return real_run(self, **kwargs)

    monkeypatch.setattr(DedupService, "run", spy)

    db = TestingSession()
    try:
        src = Source(name="p1", collection_method="rss", type="rss",
                     feed_url="https://p1.test/rss")
        db.add(src)
        db.commit()
        result = IngestionResult(source_name="p1")
        NewsIngestionPipeline(db)._record(result, src, [
            RawItem(title="Same dispatch", url=f"https://p1.test/{i}", raw_text=BODY)
            for i in (1, 2)
        ])
    finally:
        db.close()

    assert result.stored == 2 and result.errors == []
    assert len(calls) == 1 and calls[0].get("limit") == get_settings().dedup_window


def test_pipeline_path_honors_disabled_flag(monkeypatch) -> None:
    monkeypatch.setenv("DEDUP_ON_INGEST", "false")
    calls: list[dict] = []

    def spy(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(DedupService, "run", spy)

    db = TestingSession()
    try:
        src = Source(name="p2", collection_method="rss", type="rss",
                     feed_url="https://p2.test/rss")
        db.add(src)
        db.commit()
        result = IngestionResult(source_name="p2")
        NewsIngestionPipeline(db)._record(result, src, [
            RawItem(title="Same dispatch", url="https://p2.test/a", raw_text=BODY)
        ])
    finally:
        db.close()

    assert result.stored == 1 and result.errors == [] and calls == []
