"""Stage92 — deterministic domain routing + claim independence dispatch.

Offline only: in-memory SQLite, no network, no AI (routing is deterministic;
the independence engine is deterministic by design).
"""
from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import select

from backend.ai.dispatch.routing import (
    DOMAIN_NO_DISPATCH,
    DOMAIN_NO_ENGINE,
    DOMAIN_NO_SIGNAL,
    DOMAIN_TASKS,
    ROUTING_VERSION,
    TOPIC_DOMAINS,
    domain_matrix,
    persist_domain_routing,
    route_article,
)
from backend.ai.dispatch.runner import _HANDLERS, EXECUTABLE_TASKS, recover_at_startup, run_once
from backend.ai.dispatch.service import ANALYSIS_TASKS, DispatchService, logical_task, task_key
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from tests.conftest import TestingSession

_BODY = "Crude oil prices rose after the OPEC decision."


def _article(db, *, topics: list[str] | None = None, country: str | None = None,
             done: bool = True) -> Article:
    src = Source(name=f"src-{uuid.uuid4().hex[:8]}", domain="d.local", type="rss", active=True)
    db.add(src)
    db.flush()
    doc = Document(source_id=src.id, title="Oil rises", raw_text=_BODY,
                   url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(
        document_id=doc.id,
        title="Oil rises",
        summary="Crude oil prices rose today.",
        topics=json.dumps(topics) if topics is not None else None,
        country=country,
        classification_status="done" if done else "pending",
        classification_meta=json.dumps({}),
    )
    db.add(art)
    db.commit()
    return art


def _event_with_claims(db, *, source: Source, claim_source_ids: list[list[str]]):
    """One event, one article (published by ``source``), one claim per group."""
    event = Event(event_type="sanction")
    db.add(event)
    db.flush()
    doc = Document(source_id=source.id, title="t", raw_text=_BODY,
                   url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(document_id=doc.id, title="t", event_id=event.id,
                  classification_status="done", classification_meta=json.dumps({}))
    db.add(art)
    for ids in claim_source_ids:
        db.add(Claim(event_id=event.id, subject="OPEC", predicate="cuts",
                     object="supply", claim_type="economic",
                     sources=json.dumps([str(i) for i in ids])))
    db.commit()
    return art


def _orphans(db, task: str, n: int) -> None:
    """Dispatch rows for articles that no longer exist (the terminal path).

    SQLite test sessions do not enforce the FK pragma, matching how the
    runner must behave on a database that predates a cleanup.
    """
    for _ in range(n):
        db.add(ArticleDispatch(article_id=uuid.uuid4(), task_name=task_key(task),
                               status="pending"))
    db.commit()


# --- 1) the audited routing matrix ------------------------------------------

def test_every_persisted_topic_maps_to_a_matrix_domain() -> None:
    mapped = set(TOPIC_DOMAINS.values())
    assert mapped <= set(domain_matrix())


def test_matrix_honours_the_audit_no_fake_per_article_engines() -> None:
    matrix = domain_matrix()
    for _name, entry in matrix.items():
        assert entry["gap"], "every entry documents its contract/gap"
        if entry["per_article"] is False:
            assert "task" not in entry or entry["task"] is None
    # only the audited Stage93 connections may claim per-article capability
    connected = {n for n, e in matrix.items() if e["per_article"]}
    assert connected == set(DOMAIN_TASKS) == {"geopolitics", "society"}
    for name, task in DOMAIN_TASKS.items():
        assert matrix[name]["task"] == task
        assert matrix[name]["engine"], f"{name} must name its real engine path"
    # the other real aggregate engines stay honestly unconnected
    for name in ("iran", "macro", "markets"):
        assert matrix[name]["per_article"] is False


# --- 2) routing from persisted signals --------------------------------------

def test_route_uses_persisted_topics_only() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation", "geopolitics"])
        routing = route_article(art)
        assert routing["version"] == ROUTING_VERSION
        assert routing["domains"] == ["macro", "geopolitics"]
        assert routing["signals"]["topics"] == ["inflation", "geopolitics"]
        # geopolitics is Stage93-connected (per-article task); macro is not
        assert routing["state"] == "assigned"
        assert routing["signals"]["per_article_ready"] == ["geopolitics"]
        assert routing["reason_codes"] == [f"{DOMAIN_NO_DISPATCH}:macro"]
    finally:
        db.close()


def test_route_country_ir_maps_to_iran_domain() -> None:
    db = TestingSession()
    try:
        art = _article(db, country="IR")
        routing = route_article(art)
        assert "iran" in routing["domains"]
    finally:
        db.close()


def test_route_uses_persisted_event_type_signal() -> None:
    db = TestingSession()
    try:
        src = Source(name="pol-src", domain="pol.local", type="rss", active=True)
        db.add(src)
        db.flush()
        art = _event_with_claims(db, source=src, claim_source_ids=[])
        routing = route_article(art)
        # "sanction" is a POLITICAL_TYPE in the existing worldstate constants
        assert routing["signals"]["event_type"] == "sanction"
        assert "politics" in routing["domains"]
    finally:
        db.close()


def test_no_signal_yields_explicit_unassigned_state() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        routing = route_article(art)
        assert routing["domains"] == []
        assert routing["state"] == "unassigned"
        assert routing["reason_codes"] == [DOMAIN_NO_SIGNAL]
    finally:
        db.close()


def test_unknown_topics_are_ignored_not_invented() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation", "made_up_topic", "WORLD_DOMINATION"])
        routing = route_article(art)
        assert routing["signals"]["topics"] == ["inflation"]
        assert routing["domains"] == ["macro"]
    finally:
        db.close()


def test_domains_with_no_engine_get_explicit_no_engine_code() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["technology"])
        routing = route_article(art)
        assert routing["state"] == "pending"
        assert routing["reason_codes"] == [f"{DOMAIN_NO_ENGINE}:technology"]
    finally:
        db.close()


def test_relevance_and_priority_stay_separate_from_domains() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation"])
        art.document.ingestion_priority = "P0"
        db.commit()
        routing = route_article(art)
        payload = json.dumps(routing)
        # no priority and no relevance in the domain payload
        assert "priority" not in payload and "P0" not in payload
        assert "relevant" not in payload
        # reverse direction: routing never mutates priority/relevance
        assert art.document.ingestion_priority == "P0"
    finally:
        db.close()


def test_persist_writes_domain_routing_into_classification_meta() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation", "energy"])
        persist_domain_routing(db, art)
        meta = json.loads(art.classification_meta)
        routing = meta["domain_routing"]
        assert routing["domains"] == ["macro", "energy"]
        assert routing["state"] == "pending"
        assert "local_screening" not in meta  # additive beside existing keys
    finally:
        db.close()


# --- 3) the domain_routing dispatch task ------------------------------------

def test_domain_routing_task_run_and_idempotency() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation"])
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert outcome.completed == 1
        db.refresh(art)
        routing = json.loads(art.classification_meta)["domain_routing"]
        assert routing["domains"] == ["macro"]
        row = DispatchService(db).get_dispatch(art.id, "domain_routing")
        assert row.status == "completed"
        assert json.loads(row.meta)["domains"] == ["macro"]
        # a second tick never repeats completed work
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert outcome.claimed == 0
    finally:
        db.close()


def test_domain_routing_retries_until_classification_done() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation"], done=False)
        DispatchService(db).ensure_dispatch(art.id, "domain_routing")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert outcome.retryable == 1
        db.refresh(art)
        assert "domain_routing" not in json.loads(art.classification_meta)
        # classification completes; make the bounded backoff due and retry
        art.classification_status = "done"
        row = DispatchService(db).get_dispatch(art.id, "domain_routing")
        row.next_retry_at = None  # a manual retry path: due now
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert outcome.completed == 1
        db.refresh(art)
        assert json.loads(art.classification_meta)["domain_routing"]["domains"] == ["macro"]
    finally:
        db.close()


def test_domain_routing_missing_article_is_terminal() -> None:
    db = TestingSession()
    try:
        _orphans(db, "domain_routing", 1)
        outcome = asyncio.run(run_once(db, limit=5, task="domain_routing"))
        assert outcome.terminal == 1
        row = db.execute(select(ArticleDispatch).where(
            ArticleDispatch.task_name == task_key("domain_routing")
        )).scalars().one()
        assert row.status == "terminal"
        assert "article not found" in row.last_error
    finally:
        db.close()


def test_relevant_article_only_gets_the_analysis_tasks_not_every_engine() -> None:
    db = TestingSession()
    try:
        art = _article(db, topics=["inflation"])
        decision = type("D", (), {"route": "KEV", "relevant": True,
                                  "reason_codes": [], "p0_p1_safeguard": False})()
        DispatchService(db).enqueue_after_screening(art.id, decision)
        db.commit()
        rows = list(db.execute(
            select(ArticleDispatch.task_name).where(ArticleDispatch.article_id == art.id)
        ).scalars().all())
        logical = {logical_task(t) for t in rows}
        # exactly the six analysis tasks — no per-domain engine fan-out
        assert logical == set(ANALYSIS_TASKS)
        assert "domain_routing" in logical and "claim_independence" in logical
        assert not any(t.startswith(("macro@", "geopolitics@", "iran@")) for t in logical)
    finally:
        db.close()


def test_startup_recovery_derives_the_full_analysis_set() -> None:
    db = TestingSession()
    try:
        art = _article(db, done=True)
        art.classification_meta = json.dumps(
            {"local_screening": {"route": "KEV", "decision": True}})
        db.commit()
        created = recover_at_startup(db)["reenqueued"]
        assert created == len(ANALYSIS_TASKS)
        for task in ANALYSIS_TASKS:
            assert db.execute(
                select(ArticleDispatch.id).where(
                    ArticleDispatch.article_id == art.id,
                    ArticleDispatch.task_name == task_key(task))
            ).first() is not None
        assert recover_at_startup(db)["reenqueued"] == 0  # idempotent
    finally:
        db.close()


# --- 4) claim_independence through the real engine ---------------------------

def test_handler_registry_covers_every_executable_task() -> None:
    assert set(EXECUTABLE_TASKS) == set(_HANDLERS)
    assert ANALYSIS_TASKS[0] == "domain_routing"
    assert ANALYSIS_TASKS[-1] == "claim_independence"


def test_claim_independence_runs_the_real_engine() -> None:
    db = TestingSession()
    try:
        a = Source(name="A", domain="agency.local", type="rss", active=True)
        b = Source(name="B", domain="other.local", type="rss", active=True)
        db.add_all([a, b])
        db.flush()
        art = _event_with_claims(db, source=a, claim_source_ids=[[a.id, b.id]])
        DispatchService(db).ensure_dispatch(art.id, "claim_independence")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.completed == 1
        claim = db.execute(select(Claim)).scalars().one()
        # the event article's own source is in the supporting set
        assert claim.supporting_source_count == 2
        assert claim.independent_source_count == 2
        assert claim.source_independence == 1.0
        assert claim.verification_status == "corroborated"
        # completed rows are never re-run after a "restart"
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.claimed == 0
    finally:
        db.close()


def test_claim_independence_collapses_dependent_sources() -> None:
    db = TestingSession()
    try:
        # two feeds on the SAME domain are grouped by the engine's heuristic
        a = Source(name="A", domain="mirror.local", type="rss", active=True)
        c = Source(name="C", domain="mirror.local", type="rss", active=True)
        db.add_all([a, c])
        db.flush()
        art = _event_with_claims(db, source=a, claim_source_ids=[[a.id, c.id]])
        DispatchService(db).ensure_dispatch(art.id, "claim_independence")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.completed == 1
        claim = db.execute(select(Claim)).scalars().one()
        assert claim.supporting_source_count == 2
        assert claim.independent_source_count == 1  # one real corroborator only
        assert claim.verification_status == "single_source"  # never fake-corroborated
    finally:
        db.close()


def test_claim_independence_waits_for_event_dependency() -> None:
    db = TestingSession()
    try:
        art = _article(db)  # no event linked yet
        DispatchService(db).ensure_dispatch(art.id, "claim_independence")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.retryable == 1
        row = DispatchService(db).get_dispatch(art.id, "claim_independence")
        assert "event not linked" in row.last_error
    finally:
        db.close()


def test_claim_independence_with_event_but_no_claims_retries() -> None:
    db = TestingSession()
    try:
        src = Source(name="s", domain="s.local", type="rss", active=True)
        db.add(src)
        db.flush()
        art = _event_with_claims(db, source=src, claim_source_ids=[])
        DispatchService(db).ensure_dispatch(art.id, "claim_independence")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.retryable == 1
        row = DispatchService(db).get_dispatch(art.id, "claim_independence")
        assert "claims not extracted" in row.last_error
    finally:
        db.close()


def test_claim_independence_missing_article_is_terminal() -> None:
    db = TestingSession()
    try:
        _orphans(db, "claim_independence", 1)
        outcome = asyncio.run(run_once(db, limit=5, task="claim_independence"))
        assert outcome.terminal == 1
        row = db.execute(select(ArticleDispatch).where(
            ArticleDispatch.task_name == task_key("claim_independence")
        )).scalars().one()
        assert row.status == "terminal"
    finally:
        db.close()


def test_new_tasks_versioned_and_idempotent_enqueue() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        service = DispatchService(db)
        first = service.ensure_dispatch(art.id, "domain_routing")
        second = service.ensure_dispatch(art.id, "claim_independence")
        assert service.ensure_dispatch(art.id, "domain_routing").id == first.id
        assert service.ensure_dispatch(art.id, "claim_independence").id == second.id
        db.commit()
        assert first.task_name == "domain_routing@v1"
        assert second.task_name == "claim_independence@v1"
    finally:
        db.close()
