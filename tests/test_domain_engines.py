"""Stage93 — first real domain-analysis dispatch entry points.

Covers the two Stage93 connections whose engines have a legitimate bounded
per-article adapter:

* ``domain_geopolitics@v1`` -> ``GeopoliticalEngine.analyze_all(actors=[...])``
* ``domain_society@v1``    -> ``SocialEngine.analyze_all(scopes=[...])``

Offline only: in-memory SQLite, no network, no AI. Synthetic articles/events.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.ai.dispatch.routing import domain_matrix
from backend.ai.dispatch.runner import recover_at_startup, run_once
from backend.ai.dispatch.service import ANALYSIS_TASKS, DispatchService, logical_task, task_key
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.social_assessment import SocialAssessment
from backend.database.models.source import Source
from tests.conftest import TestingSession

_PERIOD = datetime.now(UTC).strftime("%Y-%m")
_BODY = "OPEC oil output decision prompts regional reaction."


def _source(db, *, domain: str = "d.local") -> Source:
    src = Source(name=f"src-{uuid.uuid4().hex[:8]}", domain=domain, type="rss", active=True)
    db.add(src)
    db.flush()
    return src


def _article(db, *, topics: list[str] | None = None, country: str | None = None,
             sentiment: float | None = None, domain: str = "d.local",
             done: bool = True) -> Article:
    doc = Document(source_id=_source(db, domain=domain).id, title="t",
                   raw_text=_BODY, url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(
        document_id=doc.id,
        title="t",
        summary="s",
        topics=json.dumps(topics) if topics is not None else None,
        country=country,
        sentiment=sentiment,
        classification_status="done" if done else "pending",
        classification_meta=json.dumps({}),
    )
    db.add(art)
    db.commit()
    return art


def _event(db, article: Article, *, actors: list[str] | None = None,
           event_type: str = "conflict") -> Event:
    event = Event(event_type=event_type,
                  actors=json.dumps(actors) if actors is not None else None)
    db.add(event)
    db.flush()
    article.event_id = event.id
    db.commit()
    return event


def _orphan(db, task: str) -> None:
    """Dispatch row whose article no longer exists (terminal path)."""
    db.add(ArticleDispatch(article_id=uuid.uuid4(), task_name=task_key(task),
                           status="pending"))
    db.commit()


def _get(db, article_id, task: str) -> ArticleDispatch:
    return DispatchService(db).get_dispatch(article_id, task)


# --- the routing step enqueues only routed domain tasks ----------------------

def test_routing_enqueues_only_routed_domain_tasks() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics", "society", "inflation"])
        decision = type("D", (), {"route": "KEV", "relevant": True,
                                  "reason_codes": [], "p0_p1_safeguard": False})()
        DispatchService(db).enqueue_after_screening(art.id, decision)
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert _get(db, art.id, "domain_geopolitics") is not None
        assert _get(db, art.id, "domain_society") is not None
        assert _get(db, art.id, "claim_independence") is not None  # base set intact
        # and nothing else: no macro/iran/... engine rows for a routed article
        rows = list(db.execute(
            select(ArticleDispatch.task_name).where(
                ArticleDispatch.article_id == art.id)
        ).scalars().all())
        assert {logical_task(t) for t in rows} == (
            set(ANALYSIS_TASKS) | {"domain_geopolitics", "domain_society"}
        )
        db.refresh(art)
        routing = json.loads(art.classification_meta)["domain_routing"]
        assert routing["reason_codes"] == ["DOMAIN_NO_DISPATCH:macro"]
    finally:
        db.close()


def test_unrouted_article_gets_no_domain_rows() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation", "technology"])
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert _get(db, art.id, "domain_geopolitics") is None
        assert _get(db, art.id, "domain_society") is None
    finally:
        db.close()


def test_routing_does_not_invent_a_domain() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["made_up_topic"])
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert _get(db, art.id, "domain_geopolitics") is None
        assert _get(db, art.id, "domain_society") is None
        routing = json.loads(art.classification_meta)["domain_routing"]
        assert routing["domains"] == []
        assert routing["state"] == "unassigned"
    finally:
        db.close()


def test_domain_tasks_versioned_and_idempotent_enqueue() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        svc = DispatchService(db)
        first = svc.ensure_dispatch(art.id, "domain_geopolitics")
        assert svc.ensure_dispatch(art.id, "domain_geopolitics").id == first.id
        db.commit()
        assert first.task_name == "domain_geopolitics@v1"
    finally:
        db.close()


# --- domain_geopolitics through the real engine ------------------------------

def test_geopolitics_task_runs_the_real_engine() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        event = _event(db, art, actors=["OPEC"])
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        row = _get(db, art.id, "domain_geopolitics")
        assert row.status == "completed"
        assessment = db.execute(select(GeopoliticalAssessment)).scalars().one()
        assert assessment.actor == "OPEC"
        assert assessment.period == _PERIOD
        assert assessment.event_count == 1
        assert assessment.method == "tension_v1"
        assert assessment.tension is not None
        assert json.loads(row.meta)["actors"] == ["OPEC"]
        # completed rows are never re-run after a "restart"
        assert asyncio.run(run_once(db, limit=5, task="domain_geopolitics")).claimed == 0
        assert event.id
    finally:
        db.close()


def test_geopolitics_bounded_adapter_recomputes_only_dispatched_actors() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        _event(db, art, actors=["OPEC"])
        _event(db, _article(db, topics=["geopolitics"]), actors=["Tokyo"])  # other actor
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        rows = list(db.execute(select(GeopoliticalAssessment)).scalars().all())
        assert [r.actor for r in rows] == ["OPEC"]  # Tokyo NOT recomputed
    finally:
        db.close()


def test_geopolitics_waits_for_the_event_dependency() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.retryable == 1
        assert "event not linked" in _get(db, art.id, "domain_geopolitics").last_error
        assert db.execute(select(GeopoliticalAssessment)).scalars().first() is None
    finally:
        db.close()


def test_geopolitics_event_without_actors_completes_with_empty_content() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        _event(db, art, actors=None)
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        row = _get(db, art.id, "domain_geopolitics")
        # completed rows carry no error text by contract; the empty content
        # is recorded in the meta instead
        meta = json.loads(row.meta)
        assert meta["actors"] == []
        assert meta["assessments_stored"] == 0 and meta["assessments_refreshed"] == 0
        assert db.execute(select(GeopoliticalAssessment)).scalars().first() is None
    finally:
        db.close()


def test_geopolitics_engine_exception_is_retryable(monkeypatch) -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        _event(db, art, actors=["OPEC"])
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()

        def boom(self, **kwargs):  # noqa: ANN001, ANN202
            raise RuntimeError("engine exploded")

        monkeypatch.setattr(
            __import__("domains.geopolitics.analysis", fromlist=["GeopoliticalEngine"]
                       ).GeopoliticalEngine, "analyze_all", boom)
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.retryable == 1
        assert db.execute(select(GeopoliticalAssessment)).scalars().first() is None
    finally:
        db.close()


def test_geopolitics_missing_article_is_terminal() -> None:
    db = TestingSession()
    try:
        _orphan(db, "domain_geopolitics")
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.terminal == 1
        row = db.execute(select(ArticleDispatch).where(
            ArticleDispatch.task_name == task_key("domain_geopolitics")
        )).scalars().one()
        assert row.status == "terminal"
    finally:
        db.close()


# --- domain_society through the real engine ----------------------------------

def test_society_task_runs_the_real_engine() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["society"], country="DE", sentiment=-0.4)
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.completed == 1
        row = _get(db, art.id, "domain_society")
        assert row.status == "completed"
        scopes = {(a.scope_type, a.scope)
                  for a in db.execute(select(SocialAssessment)).scalars().all()}
        assert scopes == {("topic", "society"), ("country", "DE")}
        topic_row = db.execute(
            select(SocialAssessment).where(
                SocialAssessment.scope_type == "topic",
                SocialAssessment.scope == "society")).scalars().one()
        assert topic_row.article_count >= 1
        assert topic_row.period == _PERIOD
    finally:
        db.close()


def test_society_bounded_adapter_recomputes_only_routed_scopes() -> None:
    db = TestingSession()
    try:
        _article(db, topics=["society"], sentiment=0.1, domain="a.local")
        _article(db, topics=["health"], sentiment=0.2, domain="b.local")  # other scope
        art = _article(db, topics=["society"], sentiment=-0.3, domain="c.local")
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_routing"))
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.completed == 1
        scopes = {(a.scope_type, a.scope)
                  for a in db.execute(select(SocialAssessment)).scalars().all()}
        assert ("topic", "health") not in scopes  # other scope NOT recomputed
        assert ("topic", "society") in scopes
    finally:
        db.close()


def test_society_waits_for_classification() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["society"], done=False)
        DispatchService(db).ensure_dispatch(art.id, "domain_society")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.retryable == 1
        assert "classification not done" in _get(
            db, art.id, "domain_society").last_error
    finally:
        db.close()


def test_society_missing_article_is_terminal() -> None:
    db = TestingSession()
    try:
        _orphan(db, "domain_society")
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.terminal == 1
    finally:
        db.close()


# --- engine matrix unchanged -------------------------------------------------

def test_unconnected_engines_stay_out_of_dispatch() -> None:
    matrix = domain_matrix()
    for name in ("iran", "macro", "markets", "energy", "technology",
                 "health", "climate", "politics"):
        assert matrix[name]["per_article"] is False
    assert set(ANALYSIS_TASKS) <= {
        "domain_routing", "event_extraction", "claim_extraction",
        "graph_extraction", "evidence_collection", "claim_independence",
    }


# --- recovery ----------------------------------------------------------------

def test_startup_recovery_derives_connected_domain_tasks() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        art.classification_meta = json.dumps({
            "local_screening": {"route": "KEV", "decision": True},
            "domain_routing": {"domains": ["society", "inflation"], "state": "pending"},
        })
        db.commit()
        created = recover_at_startup(db)["reenqueued"]
        # base analysis set + ONLY the routed+connected society task
        assert created == len(ANALYSIS_TASKS) + 1
        assert _get(db, art.id, "domain_society") is not None
        assert _get(db, art.id, "domain_geopolitics") is None
        assert recover_at_startup(db)["reenqueued"] == 0
    finally:
        db.close()
