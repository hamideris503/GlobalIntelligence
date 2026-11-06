"""Stage96 — aggregate cost optimization + pre-Stage94 routing audit.

Tests the Stage96 optimization (skip engine when assessment is already
up-to-date) and the read-only inventory of pre-Stage94 routing gaps.

Offline only: in-memory SQLite, no network, no AI.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from backend.ai.dispatch.routing import persist_domain_routing
from backend.ai.dispatch.runner import run_once
from backend.ai.dispatch.service import DispatchService
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.social_assessment import SocialAssessment
from backend.database.models.source import Source
from tests.conftest import TestingSession

_PERIOD = datetime.now(UTC).strftime("%Y-%m")
_BODY = "OPEC oil output decision prompts regional reaction."


def _source(db, domain="d.local"):
    src = Source(name=f"src-{uuid.uuid4().hex[:8]}", domain=domain, type="rss", active=True)
    db.add(src)
    db.flush()
    return src


def _article(db, topics=None, country=None, sentiment=0.0):
    doc = Document(source_id=_source(db).id, title="t", raw_text=_BODY,
                   url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(document_id=doc.id, title="t", summary="s",
                  topics=json.dumps(topics) if topics else None,
                  country=country, sentiment=sentiment,
                  classification_status="done",
                  classification_meta=json.dumps({}))
    db.add(art)
    db.commit()
    return art


def _event(db, article, actors=None, event_type="conflict"):
    event = Event(event_type=event_type,
                  actors=json.dumps(actors) if actors is not None else None)
    db.add(event)
    db.flush()
    article.event_id = event.id
    db.commit()
    return event


# --- Measurement 1: Geopolitics per-actor recomputation ----------------------

def test_measure_geopolitics_repeated_actor_work():
    """Measure how often each article triggers geopolitical analysis."""
    db = TestingSession()
    try:
        arts = []
        for _i in range(3):
            a = _article(db, topics=["geopolitics"])
            arts.append(a)
        for a in arts:
            _event(db, a, actors=["OPEC"], event_type="conflict")

        invocations = 0
        total_events_loaded = 0
        total_events_analyzed = 0
        for _ in range(3):
            events_before = db.execute(
                select(func.count()).select_from(Event)).scalar_one()
            total_events_loaded += events_before
            from domains.geopolitics.analysis import GeopoliticalEngine
            outcome = GeopoliticalEngine(db).analyze_all(actors=["OPEC"])
            invocations += 1
            total_events_analyzed += outcome.actors_analyzed

        assert total_events_loaded == 3 * events_before
        assert total_events_analyzed == 3
        assert db.execute(select(func.count()).select_from(GeopoliticalAssessment)).scalar_one() == 1
    finally:
        db.close()


# --- Measurement 2: Society per-scope recomputation --------------------------

def test_measure_society_repeated_scope_work():
    """Measure how often each article triggers society analysis."""
    db = TestingSession()
    try:
        for i in range(5):
            _article(db, topics=["society"], country="DE", sentiment=0.1 * i)

        invocations = 0
        total_articles_loaded = 0
        total_scopes_analyzed = 0
        for _ in range(3):
            articles_before = db.execute(
                select(func.count()).select_from(Article).where(
                    Article.classification_status == "done")).scalar_one()
            total_articles_loaded += articles_before
            from domains.society.analysis import SocialEngine
            outcome = SocialEngine(db).analyze_all(scopes=[("topic", "society")])
            invocations += 1
            total_scopes_analyzed += outcome.scopes_analyzed

        assert total_articles_loaded == 3 * articles_before
        assert total_scopes_analyzed == 3
        assert db.execute(select(func.count()).select_from(SocialAssessment)).scalar_one() == 1
    finally:
        db.close()


# --- Measurement 3: Bounded vs unbounded cost -------------------------------

def test_measure_bounded_vs_unbounded_cost():
    """Compare actors analyzed for bounded vs unbounded calls."""
    db = TestingSession()
    try:
        for i in range(10):
            actor = f"Actor{i}"
            for _j in range(2):
                a = _article(db, topics=["geopolitics"])
                _event(db, a, actors=[actor], event_type="conflict")

        from domains.geopolitics.analysis import GeopoliticalEngine
        outcome_all = GeopoliticalEngine(db).analyze_all()
        outcome_one = GeopoliticalEngine(db).analyze_all(actors=["Actor0"])

        assert outcome_all.actors_analyzed == 10
        assert outcome_one.actors_analyzed == 1
    finally:
        db.close()


# --- Measurement 4: Same-event repeated work ---------------------------------

def test_measure_same_event_multiple_articles():
    """Multiple articles sharing one event trigger redundant recomputation."""
    db = TestingSession()
    try:
        event = Event(event_type="conflict", actors=json.dumps(["OPEC"]))
        db.add(event)
        db.flush()
        for _i in range(5):
            a = _article(db, topics=["geopolitics"])
            a.event_id = event.id
        db.commit()

        invocations = 0
        for _ in range(5):
            from domains.geopolitics.analysis import GeopoliticalEngine
            GeopoliticalEngine(db).analyze_all(actors=["OPEC"])
            invocations += 1

        assert invocations == 5
        assert db.execute(select(func.count()).select_from(GeopoliticalAssessment)).scalar_one() == 1
    finally:
        db.close()


# --- Optimization: skip when assessment is already up-to-date ----------------

def test_geopolitics_skip_when_up_to_date():
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        row = DispatchService(db).get_dispatch(art.id, "domain_geopolitics")
        meta = json.loads(row.meta)
        assert meta.get("skipped_recompute") is not True
        assert meta["assessments_stored"] == 1

        # Second dispatch: same event (no new events) → should skip
        art2 = _article(db, topics=["geopolitics"])
        art2.event_id = art.event_id  # reuse same event
        db.commit()
        DispatchService(db).ensure_dispatch(art2.id, "domain_geopolitics")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        row2 = DispatchService(db).get_dispatch(art2.id, "domain_geopolitics")
        meta2 = json.loads(row2.meta)
        assert meta2.get("skipped_recompute") is True
        assert meta2["assessments_stored"] == 0
    finally:
        db.close()


def test_geopolitics_recomputes_when_new_event_added():
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics"])
        _event(db, art, actors=["OPEC"], event_type="conflict")
        DispatchService(db).ensure_dispatch(art.id, "domain_geopolitics")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert db.execute(select(func.count()).select_from(GeopoliticalAssessment)).scalar_one() == 1

        art2 = _article(db, topics=["geopolitics"])
        _event(db, art2, actors=["OPEC"], event_type="war")
        DispatchService(db).ensure_dispatch(art2.id, "domain_geopolitics")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_geopolitics"))
        assert outcome.completed == 1
        row = DispatchService(db).get_dispatch(art2.id, "domain_geopolitics")
        meta = json.loads(row.meta)
        assert meta.get("skipped_recompute") is not True
        assert meta["assessments_refreshed"] == 1
    finally:
        db.close()


def test_society_skip_when_up_to_date():
    db = TestingSession()
    try:
        # Create assessment manually (simulating a previous run)
        from backend.database.models.social_assessment import SocialAssessment
        sa = SocialAssessment(scope_type="topic", scope="society", period=_PERIOD,
                              avg_sentiment=0.0, article_count=1, unrest_share=0.0,
                              stance_mix="{}", method="mood_v1", confidence=0.5,
                              observed_at=datetime.now(UTC))
        db.add(sa)
        db.commit()

        # Create an article in the same scope (no country → only topic scope)
        art = _article(db, topics=["society"], sentiment=0.5)
        # Remove country to ensure only topic scope is checked
        art.country = None
        db.commit()
        DispatchService(db).ensure_dispatch(art.id, "domain_society")
        db.commit()

        # Run: should skip because assessment is already up-to-date
        # (article_count=1 matches the 1 article in the scope)
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.completed == 1
        row = DispatchService(db).get_dispatch(art.id, "domain_society")
        meta = json.loads(row.meta)
        assert meta.get("skipped_recompute") is True
    finally:
        db.close()


def test_society_recomputes_when_new_article_added():
    db = TestingSession()
    try:
        art = _article(db, topics=["society"], country="DE", sentiment=0.5)
        DispatchService(db).ensure_dispatch(art.id, "domain_society")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="domain_society"))

        art2 = _article(db, topics=["society"], country="DE", sentiment=0.3)
        DispatchService(db).ensure_dispatch(art2.id, "domain_society")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_society"))
        assert outcome.completed == 1
        row = DispatchService(db).get_dispatch(art2.id, "domain_society")
        meta = json.loads(row.meta)
        assert meta.get("skipped_recompute") is not True
    finally:
        db.close()


# --- Read-only inventory: pre-Stage94 routing coverage -----------------------

def test_inventory_pre_stage94_routing_gaps():
    """Read-only audit: classify articles by routing coverage state."""
    db = TestingSession()
    try:
        art1 = _article(db, topics=["geopolitics"])
        art1.classification_meta = json.dumps({})

        art2 = _article(db, topics=["geopolitics"])
        art2.classification_meta = json.dumps({
            "domain_routing": {"domains": ["geopolitics"], "state": "assigned",
                               "reason_codes": [], "signals": {"topics": ["geopolitics"]}},
        })

        art3 = _article(db, topics=["society"], country="DE")
        art3.classification_meta = json.dumps({
            "domain_routing": {"domains": ["society"], "state": "assigned",
                               "reason_codes": [], "signals": {"topics": ["society"]},
                               "refresh_history": [{"method": "event_driven_refresh"}]},
        })

        art4 = _article(db)
        art4.classification_meta = json.dumps({
            "domain_routing": {"domains": [], "state": "unassigned",
                               "reason_codes": ["DOMAIN_NO_SIGNAL"], "signals": {}},
        })

        db.commit()

        articles = db.execute(select(Article)).scalars().all()
        no_routing = 0
        pre_stage94 = 0
        stage94_plus = 0
        unassigned = 0
        for a in articles:
            meta = json.loads(a.classification_meta or "{}")
            dr = meta.get("domain_routing")
            if not isinstance(dr, dict):
                no_routing += 1
            elif not dr.get("refresh_history"):
                if dr.get("state") == "unassigned":
                    unassigned += 1
                else:
                    pre_stage94 += 1
            else:
                stage94_plus += 1

        assert no_routing == 1
        assert pre_stage94 == 1
        assert stage94_plus == 1
        assert unassigned == 1
    finally:
        db.close()


def test_inventory_expected_dispatch_tasks():
    """Verify expected dispatch tasks based on persisted signals only."""
    db = TestingSession()
    try:
        art = _article(db, topics=["geopolitics", "society", "inflation"])
        persist_domain_routing(db, art)
        db.commit()

        routing = json.loads(art.classification_meta)["domain_routing"]
        expected_tasks = []
        for d in routing["domains"]:
            if d in ("geopolitics", "society"):
                expected_tasks.append(d)
        assert "macro" in routing["domains"]
        assert "macro" not in expected_tasks
        assert "geopolitics" in expected_tasks
        assert "society" in expected_tasks
    finally:
        db.close()
