"""Endpoint /api/ingest/bot — روی sqlite تست، بدون لمس DB واقعی."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from tests.conftest import TestingSession


def _mk_source(name="bot-src"):
    db = TestingSession()
    s = Source(name=name, collection_method="rss", type="rss",
               feed_url="https://example.test/rss")
    db.add(s)
    db.commit()
    db.close()


def test_bot_unknown_source_404(client: TestClient):
    res = client.post("/api/ingest/bot", json={"source_name": "nope"})
    assert res.status_code == 404


def test_bot_run_single_source_sqlite(client: TestClient, monkeypatch):
    _mk_source()
    from backend.database.models.article import Article
    from backend.database.models.document import Document
    from source_bot import runner as runner_module

    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
    fixed = [RawItem(title=f"Triage dispatch {i}", url=f"https://example.test/{i}",
                     raw_text="ward logistics update " * 20,
                     metadata={"mock": False, "text_status": "full_text_extracted",
                               "identity_text": f"dispatch summary {i}"})
             for i in (1, 2, 3)]

    async def fake_fetch(plan, settings):
        return (list(fixed), "", {})

    async def no_enrich(*args, **kwargs):  # بدون شبکه: متن از قبل کامل است
        return None

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    monkeypatch.setattr(runner_module, "enrich_rss_items", no_enrich)

    def snapshot() -> dict:
        db = TestingSession()
        try:
            db.expire_all()
            return {
                d.url: (d.hash, d.content_hash, d.revision, d.retrieved_at,
                        d.duplicate_status, d.ingestion_priority, d.priority_reason,
                        d.doc_metadata)
                for d in db.query(Document).all()
            }
        finally:
            db.close()

    res = client.post("/api/ingest/bot", json={"source_name": "bot-src", "limit": 5})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sources_checked"] == 1 and body["stored"] == 3
    assert body["duplicates"] == 0 and body["sources_failed"] == {}
    before = snapshot()
    assert set(before) == {item.url for item in fixed}
    assert {row[2] for row in before.values()} == {1}
    assert {row[4] for row in before.values()} == {"new"}

    # همان ورودی ثابت، گذر دوم: هیچ رکورد/مقاله‌ای ساخته نمی‌شود و ردیف‌ها دست‌نخورده‌اند
    res2 = client.post("/api/ingest/bot", json={"source_name": "bot-src", "limit": 5})
    assert res2.status_code == 200, res2.text
    body2 = res2.json()
    assert body2["stored"] == 0 and body2["duplicates"] == 3
    assert snapshot() == before
    db = TestingSession()
    try:
        assert db.query(Document).count() == 3 and db.query(Article).count() == 3
    finally:
        db.close()


def test_bot_lock_conflict_409(client: TestClient, monkeypatch):
    import source_bot.runner as runner_module

    monkeypatch.setattr(runner_module, "_acquire_lock", lambda: False)
    res = client.post("/api/ingest/bot", json={"limit": 5})
    assert res.status_code == 409
