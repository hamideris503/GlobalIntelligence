"""Tests for Historical Memory service & API (Phase 19)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.memory import MemoryRecord
from backend.database.models.source import Source
from backend.database.models.world_state import WorldState
from domains.memory.service import HistoricalMemoryService, event_score
from tests.conftest import TestingSession


def _seed_event(surprise: float | None = 0.8) -> str:
    session = TestingSession()
    try:
        e = Event(event_type="conflict", action="bank raised rates", surprise=surprise)
        session.add(e)
        session.commit()
        return str(e.id)
    finally:
        session.close()


def _seed_article(importance: int = 9) -> str:
    import uuid as _uuid

    session = TestingSession()
    try:
        name = f"MemSrc-{_uuid.uuid4().hex[:8]}"
        src = Source(name=name, domain="m.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="x")
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id, title="big news", summary="s", importance=importance
        )
        session.add(art)
        session.commit()
        return str(art.id)
    finally:
        session.close()


def _seed_state() -> str:
    session = TestingSession()
    try:
        s = WorldState(
            captured_at=datetime.now(UTC),
            granularity="daily",
            macro_regime="expansion",
            market_regime="neutral",
            confidence=0.5,
        )
        session.add(s)
        session.commit()
        return str(s.id)
    finally:
        session.close()


# --- pure function tests ---
def test_event_score_mapping() -> None:
    assert event_score(1.0, 5) == 1.0
    assert event_score(0.0, 0) == 0.0
    assert event_score(None, 5) == 0.5
    assert event_score(0.8, 0) == 0.4


# --- service tests ---
def test_archive_events_threshold() -> None:
    _seed_event(surprise=0.9)  # score 0.45+ -> archived
    _seed_event(surprise=0.0)  # score 0.0 -> skipped
    session = TestingSession()
    try:
        outcome = HistoricalMemoryService(session).archive_events()
        assert outcome.events_archived == 1
        rec = session.query(MemoryRecord).one()
        assert rec.layer == "event"
        assert rec.importance is not None and rec.importance >= 0.3
    finally:
        session.close()


def test_archive_is_idempotent() -> None:
    _seed_event(surprise=0.9)
    _seed_state()
    _seed_article(importance=9)
    session = TestingSession()
    try:
        first = HistoricalMemoryService(session).archive_all()
        assert first.events_archived == 1
        assert first.states_archived == 1
        assert first.raw_archived == 1
        second = HistoricalMemoryService(session).archive_all()
        assert second.events_archived == 0
        assert second.states_archived == 0
        assert second.raw_archived == 0
        assert second.duplicates == 3
        assert session.query(MemoryRecord).count() == 3
    finally:
        session.close()


def test_archive_raw_threshold() -> None:
    _seed_article(importance=9)  # archived
    _seed_article(importance=3)  # skipped
    session = TestingSession()
    try:
        outcome = HistoricalMemoryService(session).archive_raw()
        assert outcome.raw_archived == 1
    finally:
        session.close()


def test_timeline_as_of_filters_future() -> None:
    _seed_event(surprise=0.9)
    session = TestingSession()
    try:
        HistoricalMemoryService(session).archive_events()
        past = datetime.now(UTC) - timedelta(days=365)
        future = datetime.now(UTC) + timedelta(days=1)
        assert HistoricalMemoryService(session).timeline(as_of=past) == []
        assert len(HistoricalMemoryService(session).timeline(as_of=future)) == 1
    finally:
        session.close()


def test_timeline_layer_filter() -> None:
    _seed_event(surprise=0.9)
    _seed_state()
    session = TestingSession()
    try:
        HistoricalMemoryService(session).archive_all()
        future = datetime.now(UTC) + timedelta(days=1)
        events = HistoricalMemoryService(session).timeline(as_of=future, layer="event")
        states = HistoricalMemoryService(session).timeline(as_of=future, layer="state")
        assert len(events) == 1 and len(states) == 1
    finally:
        session.close()


def test_stats() -> None:
    _seed_event(surprise=0.9)
    session = TestingSession()
    try:
        HistoricalMemoryService(session).archive_all()
        stats = HistoricalMemoryService(session).stats()
        assert stats == {"event": 1}
    finally:
        session.close()


# --- API tests ---
def test_memory_api_archive_timeline_stats(client: TestClient) -> None:
    _seed_event(surprise=0.9)
    res = client.post("/api/memory/archive")
    assert res.status_code == 200
    assert res.json()["events_archived"] == 1

    stats = client.get("/api/memory/stats")
    assert stats.status_code == 200
    assert stats.json() == {"event": 1}

    future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tl = client.get(f"/api/memory/timeline?as_of={future}")
    assert tl.status_code == 200
    assert len(tl.json()) == 1

    recs = client.get("/api/memory/records?layer=event")
    assert recs.status_code == 200
    assert len(recs.json()) == 1


def test_memory_api_timeline_naive_rejected(client: TestClient) -> None:
    res = client.get("/api/memory/timeline?as_of=2026-10-08T00:00:00")
    assert res.status_code == 422
