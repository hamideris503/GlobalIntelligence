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
    from source_bot import runner as runner_module

    async def fake_fetch(plan, settings):
        return ([RawItem(title="Triage dispatch", url="https://example.test/1",
                         raw_text="ward logistics update " * 20)], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    res = client.post("/api/ingest/bot", json={"source_name": "bot-src", "limit": 5})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sources_checked"] == 1 and body["stored"] == 1
    assert body["sources_failed"] == {}
    # تکرار -> تکراری، بدون رکورد جدید
    res2 = client.post("/api/ingest/bot", json={"source_name": "bot-src", "limit": 5})
    assert res2.json()["stored"] == 0 and res2.json()["duplicates"] == 1


def test_bot_lock_conflict_409(client: TestClient, monkeypatch):
    import source_bot.runner as runner_module

    monkeypatch.setattr(runner_module, "_acquire_lock", lambda: False)
    res = client.post("/api/ingest/bot", json={"limit": 5})
    assert res.status_code == 409
