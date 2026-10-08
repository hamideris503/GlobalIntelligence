"""Tests for event extraction (Phase 11)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.events.extractor import EventExtractor, _parse_dt
from domains.events.prompts import EVENT_SCHEMA
from tests.conftest import TestingSession


def _seed_cluster(cluster: str, texts: list[str]) -> None:
    session = TestingSession()
    try:
        src = Source(name=f"Src-{cluster}", domain="e.local", type="rss", active=True)
        session.add(src)
        session.flush()
        for i, text in enumerate(texts):
            doc = Document(source_id=src.id, title=f"t{i}", raw_text=text)
            session.add(doc)
            session.flush()
            session.add(
                Article(
                    document_id=doc.id,
                    title=f"t{i}",
                    summary=text,
                    topics=json.dumps(["markets"]),
                    importance=3,
                    duplicate_cluster=cluster,
                    classification_status="done",
                )
            )
        session.commit()
    finally:
        session.close()


def test_event_schema_is_object() -> None:
    assert EVENT_SCHEMA["type"] == "object"
    assert "event_type" in EVENT_SCHEMA["required"]


def test_parse_dt_variants() -> None:
    assert _parse_dt("2026-10-08T10:00:00Z") is not None
    assert _parse_dt(None) is None
    assert _parse_dt("not-a-date") is None


def test_extract_creates_event_for_cluster() -> None:
    _seed_cluster("c1", ["oil rises on supply", "oil climbs amid supply worries"])
    session = TestingSession()
    try:
        outcome = asyncio.run(EventExtractor(session).run(limit=10))
        assert outcome.events_created == 1
        assert outcome.articles_linked == 2
        events = session.query(Event).all()
        assert len(events) == 1
        # همه‌ی مقالات خوشه به رویداد وصل شده‌اند
        linked = session.query(Article).filter(Article.event_id == events[0].id).count()
        assert linked == 2
    finally:
        session.close()


def test_extract_ignores_unclassified() -> None:
    session = TestingSession()
    try:
        src = Source(name="S2", domain="e.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="x", raw_text="x")
        session.add(doc)
        session.flush()
        session.add(
            Article(document_id=doc.id, title="x", summary="x",
                    classification_status="pending")
        )
        session.commit()
    finally:
        session.close()

    session = TestingSession()
    try:
        outcome = asyncio.run(EventExtractor(session).run(limit=10))
        assert outcome.events_created == 0
    finally:
        session.close()


def test_events_api(client: TestClient) -> None:
    _seed_cluster("c2", ["fed holds rates steady today"])
    res = client.post("/api/events/extract?limit=10")
    assert res.status_code == 200
    assert res.json()["events_created"] == 1

    listing = client.get("/api/events")
    assert listing.status_code == 200
    events = listing.json()
    assert len(events) == 1
    assert events[0]["article_count"] == 1
