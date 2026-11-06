"""Validation anti-hallucination de l'extraction AI (mocked gateway)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.events.extractor import EventExtractor
from tests.conftest import TestingSession


class FakeGateway:
    def __init__(self, structured):
        self._structured = structured

    async def structured_generate(self, request, schema):
        return SimpleNamespace(
            is_mock=False,
            structured=self._structured,
            text=json.dumps(self._structured),
            provider="fake",
            model="fake-1",
            latency_ms=1.0,
        )


@pytest.mark.asyncio
async def test_invalid_event_type_rejected_and_fallback_rules(monkeypatch) -> None:
    monkeypatch.setattr("domains.events.extractor.effective_mock_mode", lambda: False)
    session = TestingSession()
    src = Source(name="s", feed_url="https://example.com/feed.xml", type="rss")
    session.add(src)
    session.flush()
    doc = Document(source_id=src.id, url="https://example.com/a", title="t")
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="OPEC cuts oil production, crude prices rise",
                  summary="OPEC announced cuts.", classification_status="done")
    session.add(art)
    session.commit()

    ext = EventExtractor(session)
    ext.gateway = FakeGateway({"event_type": "not_a_type", "location": None,
                              "action": "x", "actors": [], "confidence": 0.9})
    outcome = await ext.run(limit=10)
    assert outcome.events_created == 1
    ev = session.query(Event).first()
    assert ev.event_type == "energy"
    meta = json.loads(ev.event_metadata)
    assert "invalid_event_type" in (meta.get("validation_issues") or [])
    session.close()


@pytest.mark.asyncio
async def test_location_not_in_text_rejected(monkeypatch) -> None:
    monkeypatch.setattr("domains.events.extractor.effective_mock_mode", lambda: False)
    session = TestingSession()
    src = Source(name="s2", feed_url="https://example.com/feed2.xml", type="rss")
    session.add(src)
    session.flush()
    doc = Document(source_id=src.id, url="https://example.com/b", title="t")
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="Federal Reserve raises rates",
                  summary="Inflation surges.", classification_status="done")
    session.add(art)
    session.commit()

    ext = EventExtractor(session)
    ext.gateway = FakeGateway({"event_type": "economic", "location": "Paris",
                              "action": "x", "actors": [], "confidence": 0.9})
    await ext.run(limit=10)
    ev = session.query(Event).first()
    assert ev.location is None
    meta = json.loads(ev.event_metadata)
    assert "location_not_in_text" in (meta.get("validation_issues") or [])
    session.close()


@pytest.mark.asyncio
async def test_ai_vs_rules_conflict_recorded(monkeypatch) -> None:
    monkeypatch.setattr("domains.events.extractor.effective_mock_mode", lambda: False)
    session = TestingSession()
    src = Source(name="s3", feed_url="https://example.com/feed3.xml", type="rss")
    session.add(src)
    session.flush()
    doc = Document(source_id=src.id, url="https://example.com/c", title="t")
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="OPEC cuts oil production",
                  summary="Crude prices rise.", classification_status="done")
    session.add(art)
    session.commit()

    ext = EventExtractor(session)
    ext.gateway = FakeGateway({"event_type": "conflict", "location": None,
                              "action": "x", "actors": [], "confidence": 0.9})
    await ext.run(limit=10)
    ev = session.query(Event).first()
    meta = json.loads(ev.event_metadata)
    avr = meta.get("ai_vs_rules")
    assert avr is not None
    assert avr.get("conflict") is True
    assert "ai_rules_conflict" in (meta.get("review_flags") or [])
    session.close()
