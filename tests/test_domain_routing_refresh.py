"""Stage94 — event-driven domain routing refresh.

Tests that domain-relevant signals materializing *after* initial domain
routing (event actors / event_type persisted by event extraction) trigger a
durable routing refresh that creates only the missing domain dispatch rows.

Offline only: in-memory SQLite, no network, no AI. Events are created
directly (deterministic) except for one wiring test that monkeypatches the
real EventExtractor to confirm the refresh row is enqueued after event
persistence.
"""
from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import select

from backend.ai.dispatch.runner import _HANDLERS, EXECUTABLE_TASKS, run_once
from backend.ai.dispatch.service import (
    ANALYSIS_TASKS,
    DispatchService,
    task_key,
)
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from tests.conftest import TestingSession

_BODY = "OPEC oil output decision prompts regional reaction."


def _source(db, *, domain: str = "d.local") -> Source:
    src = Source(name=f"src-{uuid.uuid4().hex[:8]}", domain=domain, type="rss", active=True)
    db.add(src)
    db.flush()
    return src


def _article(db, *, topics: list[str] | None = None, country: str | None = None,
             done: bool = True) -> Article:
    doc = Document(source_id=_source(db).id, title="t", raw_text=_BODY,
                   url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(
        document_id=doc.id,
        title="t",
        summary="s",
        topics=json.dumps(topics) if topics is not None else None,
        country=country,
        classification_status="done" if done else "pending",
        classification_meta=json.dumps({}),
    )
    db.add(art)
    db.commit()
    return art


def _event(db, article: Article, *, actors: list[str] | None = None,
           event_type: str = "conflict") -> Event:
    """Create a real persisted Event linked to the article."""
    event = Event(event_type=event_type,
                  actors=json.dumps(actors) if actors is not None else None)
    db.add(event)
    db.flush()
    article.event_id = event.id
    db.commit()
    return event


def _count_rows(db, article_id, task: str) -> int:
    return int(db.execute(
        select(ArticleDispatch.id).where(
            ArticleDispatch.article_id == article_id,
            ArticleDispatch.task_name == task_key(task),
        )
    ).scalars().all().__len__())


def _routing(db, article_id: str) -> dict:
    row = db.get(Article, uuid.UUID(article_id))
    meta = json.loads(row.classification_meta or "{}")
    return meta.get("domain_routing", {})


# --- 1) initial routing with no available domain signal ----------------------

def test_initial_routing_no_signal_is_unassigned() -> None:
    db = TestingSession()
    try:
        art = _article(db)  # no topics, no country
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        routing = _routing(db, str(art.id))
        assert routing["domains"] == []
        assert routing["state"] == "unassigned"
        assert routing["reason_codes"] == ["DOMAIN_NO_SIGNAL"]
    finally:
        db.close()


# --- 2+3) post-event routing creates missing domain dispatch -----------------

def test_post_event_routing_creates_geopolitics_dispatch() -> None:
    db = TestingSession()
    try:
        art = _article(db)  # no domain signals yet
        # Initial routing: unassigned, no domain tasks
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert _routing(db, str(art.id))["state"] == "unassigned"
        assert _count_rows(db, art.id, "domain_geopolitics") == 0

        # Event extraction persists a conflict event with an actor
        _event(db, art, actors=["OPEC"], event_type="conflict")

        # Post-event routing refresh: geopolitics now justified, task created
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert outcome.completed == 1
        assert _count_rows(db, art.id, "domain_geopolitics") == 1
        row = DispatchService(db).get_dispatch(art.id, "domain_geopolitics")
        assert row.status == "pending"  # created, not yet run

        routing = _routing(db, str(art.id))
        assert "geopolitics" in routing["domains"]
        assert routing["state"] == "assigned"
        assert routing["reason_codes"] == []  # DOMAIN_NO_SIGNAL cleared
        assert any(h["triggered_by_event"] == str(art.event_id)
                   for h in routing["refresh_history"])
    finally:
        db.close()


def test_post_event_refresh_updates_metadata_without_overwriting_screening() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        # Pre-existing screening provenance must survive
        art.classification_meta = json.dumps({
            "local_screening": {
                "route": "KEV", "decision": True, "reason_codes": ["KEV_RELEVANT"],
            },
        })
        art.document.ingestion_priority = "P0"
        db.commit()

        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))

        meta = json.loads(db.get(Article, art.id).classification_meta)
        assert meta["local_screening"]["route"] == "KEV"  # preserved
        assert meta["local_screening"]["decision"] is True  # preserved
        assert art.document.ingestion_priority == "P0"  # priority untouched
        assert "geopolitics" in meta["domain_routing"]["domains"]
    finally:
        db.close()


# --- 4) completed tasks are not duplicated by refresh -------------------------

def test_refresh_does_not_duplicate_completed_domain_task() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        _event(db, art, actors=["OPEC"], event_type="conflict")
        # Create + complete the domain task
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert DispatchService(db).get_dispatch(art.id, "domain_geopolitics").status == "completed"

        # Refresh runs again (re-computes routing) but must not create a second row
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert _count_rows(db, art.id, "domain_geopolitics") == 1
    finally:
        db.close()


# --- 5) repeating the same completion callback is idempotent ------------------

def test_refresh_enqueue_is_idempotent() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        first = svc.ensure_dispatch(art.id, "domain_routing_refresh")
        second = svc.ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        assert first.id == second.id
        assert first.task_name == "domain_routing_refresh@v1"
        assert _count_rows(db, art.id, "domain_routing_refresh") == 1
    finally:
        db.close()


# --- 6) event-extraction retry producing more events triggers refresh ---------

def test_refresh_picks_up_newly_added_event_actors() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        # First event with no actors → refresh finds nothing new
        _event(db, art, actors=None, event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        # event_type=conflict still routes geopolitics even without actors
        assert _count_rows(db, art.id, "domain_geopolitics") == 1

        # Same article, refresh again with actor info already on event:
        # no duplicate (already tracked)
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert _count_rows(db, art.id, "domain_geopolitics") == 1
    finally:
        db.close()


# --- 7) empty actors never invoke unbounded global batch ---------------------

def test_empty_actors_refresh_completes_without_unbounded_batch() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        _event(db, art, actors=[], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert outcome.completed == 1
        # geopolitics is routed (from event_type) but the task completes with
        # empty content — the Stage93 safeguard prevents the unbounded batch.
        row = DispatchService(db).get_dispatch(art.id, "domain_geopolitics")
        assert row is not None
        asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        row = DispatchService(db).get_dispatch(art.id, "domain_geopolitics")
        assert row.status == "completed"
        assert json.loads(row.meta)["actors"] == []
    finally:
        db.close()


# --- 8) the actual dispatch consumer runs the refresh handler -----------------

def test_dispatch_consumer_runs_refresh_handler() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert outcome.completed == 1
        assert outcome.tasks["domain_routing_refresh"]["completed"] == 1
        assert _count_rows(db, art.id, "domain_geopolitics") == 1
    finally:
        db.close()


# --- 9) refresh failure becomes retryable / terminal --------------------------

def test_refresh_failure_is_retryable(monkeypatch) -> None:
    db = TestingSession()
    try:
        art = _article(db)
        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()

        def boom(self, **kwargs):  # noqa: ANN001, ANN202
            raise RuntimeError("engine exploded")

        monkeypatch.setattr(
            __import__("domains.geopolitics.analysis", fromlist=["GeopoliticalEngine"]
                       ).GeopoliticalEngine, "analyze_all", boom)

        # The refresh itself creates the domain_geopolitics row; running that
        # task hits the mocked engine and becomes retryable.
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert _count_rows(db, art.id, "domain_geopolitics") == 1
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.retryable == 1
    finally:
        db.close()


# --- 10) crash recovery: idempotent enqueue survives restart ------------------

def test_refresh_survives_restart_without_duplicates() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        # First "run" completes
        asyncio.run(run_once(db, limit=5, task="domain_routing_refresh"))
        assert _count_rows(db, art.id, "domain_routing_refresh") == 1

        # "Restart": new session, same durable store — refresh row already
        # completed, nothing reclaimed or duplicated.
        db2 = TestingSession()
        try:
            outcome = asyncio.run(run_once(db2, limit=5, task="domain_routing_refresh"))
            assert outcome.claimed == 0
            row = DispatchService(db2).get_dispatch(art.id, "domain_routing_refresh")
            assert row is not None and row.status == "completed"
        finally:
            db2.close()
    finally:
        db.close()


# --- 11) concurrent refresh callbacks do not create duplicates ----------------

def test_concurrent_refresh_enqueue_no_duplicates() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        # Simulate two concurrent completion callbacks
        row1 = svc.ensure_dispatch(art.id, "domain_routing_refresh")
        row2 = svc.ensure_dispatch(art.id, "domain_routing_refresh")
        db.commit()
        assert row1.id == row2.id
        assert _count_rows(db, art.id, "domain_routing_refresh") == 1
    finally:
        db.close()


# --- 12) domains without real handlers receive no placeholder tasks -----------

def test_unconnected_domain_gets_no_placeholder_task() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation"])  # macro — unconnected
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        # macro is routed but has no per-article engine: no task row, reason code only
        assert _count_rows(db, art.id, "domain_geopolitics") == 0
        # There's no "macro" task at all (no placeholder)
        assert _count_rows(db, art.id, "domain_geopolitics") == 0
        routing = _routing(db, str(art.id))
        assert "macro" in routing["domains"]
        assert any(c == "DOMAIN_NO_DISPATCH:macro" for c in routing["reason_codes"])
    finally:
        db.close()


# --- wiring: event extraction enqueues the refresh row -------------------------

def test_event_extraction_enqueues_refresh_after_persistence(monkeypatch) -> None:
    """The event-extraction handler enqueues domain_routing_refresh once the
    event row exists. Verified by monkeypatching the real EventExtractor."""
    from domains.events.extractor import EventExtractor

    db = TestingSession()
    try:
        art = _article(db)
        assert _count_rows(db, art.id, "domain_routing_refresh") == 0

        class FakeOutcome:
            events_created = 1

        async def fake_run(self, *, limit, article_ids=None):  # noqa: ANN001, ANN202
            # Simulate the extractor persisting an event linked to the article
            event = Event(event_type="conflict", actors=json.dumps(["OPEC"]))
            db.add(event)
            db.flush()
            article = db.get(Article, article_ids[0])
            article.event_id = event.id
            db.commit()
            return FakeOutcome()

        monkeypatch.setattr(EventExtractor, "run", fake_run)

        DispatchService(db).ensure_dispatch(art.id, "event_extraction")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="event_extraction"))
        assert outcome.completed == 1
        # Refresh row enqueued durably after event persistence
        assert _count_rows(db, art.id, "domain_routing_refresh") == 1
    finally:
        db.close()


# --- matrix / task conventions ----------------------------------------------

def test_refresh_task_is_executable_and_ordered_after_event() -> None:
    assert "domain_routing_refresh" in EXECUTABLE_TASKS
    assert "domain_routing_refresh" in _HANDLERS
    # Ordered after event_extraction, before claim_extraction
    order = list(EXECUTABLE_TASKS)
    assert order.index("event_extraction") < order.index("domain_routing_refresh")
    assert order.index("domain_routing_refresh") < order.index("claim_extraction")
    # Never produced by screening enqueue
    assert "domain_routing_refresh" not in ANALYSIS_TASKS
