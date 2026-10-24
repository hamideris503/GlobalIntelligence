"""Integration: deliver به pipeline موجود + provenance + lock + migration سازگار."""
from __future__ import annotations

import json
import os

from backend.database.base import Base
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot.output import deliver, merge_priority_metadata
from source_bot.registry import pick_adapter
from source_bot.runner import LOCK_PATH as _LOCK_PATH
from source_bot.runner import _acquire_lock, _release_lock


def _mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_due_sources_applies_limit_after_due_filter():
    """limit بعد از فیلتر due اعمال میشود؛ منابع تازه سهم منابع due را نمیخورند."""
    from datetime import UTC, datetime, timedelta

    from source_bot.registry import due_sources

    db = _mem_db()
    now = datetime.now(UTC)
    db.add_all([
        Source(name="a-fresh", collection_method="rss", type="rss", active=True, last_success=now),
        Source(name="b-fresh", collection_method="rss", type="rss", active=True, last_success=now),
        Source(name="y-old", collection_method="rss", type="rss", active=True,
               last_success=now - timedelta(hours=5)),
        Source(name="z-never", collection_method="rss", type="rss", active=True),
    ])
    db.commit()

    assert [s.name for s in due_sources(db, interval_seconds=3600, limit=1)] == ["y-old"]
    assert {s.name for s in due_sources(db, interval_seconds=3600, limit=50)} == {"y-old", "z-never"}


def test_pick_adapter_single_owner():
    s = Source(name="n1", feed_url="https://ex.com/rss", collection_method="rss", type="rss")
    assert pick_adapter(s).adapter == "rss"
    s2 = Source(name="n2", api_url="https://ex.com/api", collection_method="api", type="api")
    assert pick_adapter(s2).adapter == "rest_json"
    s3 = Source(name="n3", collection_method="rss", type="rss")
    assert pick_adapter(s3).adapter == "skip"


def test_api_with_api_url_uses_rest_json():
    """اولویت api_url صریح حتی با وجود feed (حفظ مالکیت مسیر تخصصی)."""
    s = Source(name="t1", collection_method="api", type="api",
               api_url="https://example.test/api",
               feed_url="https://example.test/f.xml")
    plan = pick_adapter(s)
    assert plan.adapter == "rest_json" and plan.url == "https://example.test/api"


def test_api_without_api_url_with_feed_falls_back_to_rss():
    """حالت BLS: متد api بدون api_url ولی با feed معتبر → rss."""
    s = Source(name="t2", collection_method="api", type="official",
               feed_url="https://example.test/f.xml")
    plan = pick_adapter(s)
    assert plan.adapter == "rss" and plan.url == "https://example.test/f.xml"


def test_api_without_feed_nor_api_url_stays_specialized():
    """قفل مالکیت تخصصی: api بدون هیچ endpoint → specialized (حالت FRED)."""
    s = Source(name="t3", collection_method="api", type="api")
    plan = pick_adapter(s)
    assert plan.adapter == "specialized" and plan.url is None


def test_old_model_without_census_columns_never_raises():
    """مدل قدیمی (بدون api_url/rss_url/homepage/data_download_url) نباید
    AttributeError بدهد؛ رفتار با مدل جدید یکسان است (رگرسیون prod)."""
    from types import SimpleNamespace

    def old_model(**kw):
        base = dict(collection_method="api", type="official",
                    feed_url="https://example.test/f.xml")
        base.update(kw)
        return SimpleNamespace(**base)

    plan = pick_adapter(old_model())
    assert plan.adapter == "rss" and plan.url == "https://example.test/f.xml"
    plan = pick_adapter(old_model(collection_method="api", type="api",
                                  feed_url=None))
    assert plan.adapter == "specialized"
    plan = pick_adapter(old_model(collection_method="scrape", type="official",
                                  feed_url=None))
    assert plan.adapter == "skip"


def test_deliver_to_existing_pipeline_and_provenance():
    db = _mem_db()
    src = Source(name="t-src", collection_method="rss", type="rss", feed_url="https://ex.com/rss")
    db.add(src)
    db.commit()
    item = RawItem(title="T", url="https://ex.com/a", raw_text="body text here", metadata={})
    assert deliver(db, src, item, priority="P2", score=60.0, reason="r",
                   priority_source="rules", priority_status="RULES_ONLY",
                   duplicate_status="new", canonical_url="https://ex.com/a") is True
    # دوباره همان محتوا -> تکراری درون منبع
    from domains.news.ingestion import NewsIngestionPipeline

    assert NewsIngestionPipeline(db).store_item(src, item) is False
    docs = db.query(Document).all()
    assert len(docs) == 1
    meta = json.loads(docs[0].doc_metadata or "{}")
    assert meta["ingestion_priority"] == "P2"  # provenance حفظ شده


def test_merge_metadata_no_data_loss():
    out = merge_priority_metadata('{"a": 1}', {"ingestion_priority": "P0"})
    assert json.loads(out)["a"] == 1


def test_lock_prevents_concurrent_run():
    assert _acquire_lock() is True
    assert _acquire_lock() is False
    _release_lock()
    assert _acquire_lock() is True
    _release_lock()


def _write_lock(content: str) -> None:
    with open(_LOCK_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_lock_live_owner_is_never_stolen():
    try:
        assert _acquire_lock() is True
        assert _acquire_lock() is False
        with open(_LOCK_PATH, encoding="utf-8") as fh:
            assert fh.read().strip().split()[0] == str(os.getpid())
    finally:
        _release_lock()


def test_lock_stale_dead_pid_is_reclaimed():
    try:
        _write_lock(str(2 ** 30))  # چنین PID‌ی قطعاً وجود ندارد
        assert _acquire_lock() is True
    finally:
        _release_lock()


def test_lock_garbage_content_is_never_stolen():

    try:
        _write_lock("not-a-pid")
        assert _acquire_lock() is False
        with open(_LOCK_PATH, encoding="utf-8") as fh:
            assert fh.read() == "not-a-pid"
    finally:
        try:
            os.remove(_LOCK_PATH)
        except OSError:
            pass


def test_lock_concurrent_acquire_single_winner():
    import threading

    results = []
    try:
        threads = [threading.Thread(target=lambda: results.append(_acquire_lock()))
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count(True) == 1
    finally:
        _release_lock()


def test_ai_gateway_not_called_for_clear_rules():
    from datetime import UTC, datetime

    from source_bot.priority_engine import score_item

    r = score_item(title="central bank raises interest rates sharply",
                   body=("detailed market analysis with complete data " * 60),
                   published_at=datetime.now(UTC), has_author=True)
    assert r.needs_ai is False  # پس runner نباید gateway را صدا بزند
