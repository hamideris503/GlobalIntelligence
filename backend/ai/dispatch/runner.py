"""Downstream dispatch runner (Stage89).

Consumes ``article_dispatches`` rows and invokes the *existing* domain
components — never copies of them:

* ``screening``           -> ``local_screening.orchestrator.screen_with_db``
* ``domain_routing``      -> ``dispatch.routing.persist_domain_routing`` (Stage92)
* ``event_extraction``    -> ``domains.events.extractor.EventExtractor``
* ``claim_extraction``    -> ``domains.claims.extractor.ClaimExtractor``
* ``graph_extraction``    -> ``domains.graph.engine.KnowledgeGraphEngine``
* ``evidence_collection`` -> ``domains.claims.evidence.EvidenceEngine``
* ``domain_geopolitics``  -> ``domains.geopolitics.analysis.GeopoliticalEngine`` (Stage93)
* ``domain_society``      -> ``domains.society.analysis.SocialEngine`` (Stage93)
* ``claim_independence``  -> ``domains.news.independence.SourceIndependenceEngine``

The extractors run in their normal batch form with a one-article/one-event
filter, so their guards, prompts, commit points and provenance behaviour stay
in one place. Results are tracked per (article, task, analysis version); a
retry never repeats a completed target.

``domain_routing`` fans out to NO engine: it derives domains from the already
persisted classification signals (topics/country/event_type) and records the
routing — state and reason codes — in ``classification_meta``. For each routed
domain it creates ONLY the dispatch rows in ``DOMAIN_TASKS`` (Stage93:
geopolitics, society); unconnected aggregate engines (macro, risk, iran brief,
...) keep explicit reason codes instead of a fake fan-out.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.dispatch.service import (
    ANALYSIS_TASKS,
    EXECUTABLE_TASKS,
    DispatchService,
    LogicalTask,
    logical_task,
)
from backend.core.logging import get_logger

logger = get_logger(__name__)

HandlerStatus = Literal["completed", "retryable", "terminal"]


@dataclass
class HandlerResult:
    status: HandlerStatus
    detail: str = ""
    meta: dict[str, Any] | None = None


@dataclass
class DispatchOutcome:
    claimed: int = 0
    completed: int = 0
    retryable: int = 0
    terminal: int = 0
    tasks: dict[str, dict[str, int]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claimed": self.claimed,
            "completed": self.completed,
            "retryable": self.retryable,
            "terminal": self.terminal,
            "tasks": self.tasks,
        }


# --- helpers -----------------------------------------------------------------

def _article(db: Session, article_id: uuid.UUID):
    from backend.database.models.article import Article

    return db.get(Article, article_id)


def _merge_classification_meta(article, screening_decision: dict[str, Any]) -> None:
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta["local_screening"] = screening_decision
    article.classification_meta = json.dumps(meta, ensure_ascii=False)


# --- handlers ----------------------------------------------------------------

async def _handle_screening(db: Session, dispatch) -> HandlerResult:
    """Re-run screening for an article whose first attempt was unavailable."""
    from domains.news.classifier import _article_text, _doc_priority

    from backend.ai.local_screening.orchestrator import screen_with_db

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    level, _ = _doc_priority(article)
    text = _article_text(article)
    if not text.strip():
        return HandlerResult("terminal", "article text is empty")

    decision = await screen_with_db(db, text, level)
    _merge_classification_meta(article, decision.as_dict())
    db.flush()

    if decision.relevant is None:
        reasons = ",".join(decision.reason_codes[-3:]) or "unknown"
        return HandlerResult(
            "retryable", f"screening unavailable: {reasons}",
            meta={"screening_route": decision.route})
    if decision.relevant is True:
        DispatchService(db).enqueue_after_screening(article.id, decision)
    return HandlerResult(
        "completed", "",
        meta={
            "screening_route": decision.route,
            "screening_decision": decision.relevant,
            "screening_reason_codes": decision.reason_codes,
        })


async def _handle_event_extraction(db: Session, dispatch) -> HandlerResult:
    from domains.events.extractor import EventExtractor

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is not None:
        return HandlerResult("completed", "", meta={"event_id": str(article.event_id)})
    if article.classification_status != "done":
        return HandlerResult("retryable", "classification not done")

    outcome = await EventExtractor(db).run(limit=1, article_ids=[article.id])
    db.refresh(article)
    if article.event_id is not None:
        # Stage94: durable post-event routing refresh — enqueued only after the
        # event row exists. Idempotent: the unique key keeps one refresh row per
        # article even if this completion path is reached again (retry, restart).
        DispatchService(db).ensure_dispatch(article.id, "domain_routing_refresh")
        return HandlerResult(
            "completed", "",
            meta={"event_id": str(article.event_id),
                  "events_created": outcome.events_created})
    if outcome.skipped:
        # Explicit mock provenance in production is a permanent skip, not a
        # transient failure that will retry forever.
        return HandlerResult("terminal", "event extraction skipped (mock provenance)")
    detail = outcome.errors[0] if outcome.errors else "event not created yet"
    return HandlerResult("retryable", detail)


async def _handle_claim_extraction(db: Session, dispatch) -> HandlerResult:
    from domains.claims.extractor import ClaimExtractor

    from backend.database.models.event import Event

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")
    event = db.get(Event, article.event_id)
    if event is None:
        return HandlerResult("retryable", "event row missing")
    if event.claims_extracted:
        return HandlerResult("completed", "", meta={"event_id": str(event.id)})

    outcome = await ClaimExtractor(db).run(limit=1, event_ids=[event.id])
    db.refresh(event)
    if event.claims_extracted:
        return HandlerResult(
            "completed", "",
            meta={"event_id": str(event.id), "claims_created": outcome.claims_created})
    if outcome.skipped:
        return HandlerResult("terminal", "claim extraction skipped (mock provenance)")
    detail = outcome.errors[0] if outcome.errors else "claims not extracted yet"
    return HandlerResult("retryable", detail)


async def _handle_graph_extraction(db: Session, dispatch) -> HandlerResult:
    from domains.graph.engine import KnowledgeGraphEngine

    from backend.database.models.event import Event

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")
    event = db.get(Event, article.event_id)
    if event is None:
        return HandlerResult("retryable", "event row missing")
    if event.graph_extracted:
        return HandlerResult("completed", "", meta={"event_id": str(event.id)})

    outcome = await KnowledgeGraphEngine(db).run(limit=1, event_ids=[event.id])
    db.refresh(event)
    if event.graph_extracted:
        return HandlerResult(
            "completed", "",
            meta={
                "event_id": str(event.id),
                "entities_created": outcome.entities_created,
                "relationships_created": outcome.relationships_created,
            })
    detail = outcome.errors[0] if outcome.errors else "graph not extracted yet"
    return HandlerResult("terminal" if outcome.failed else "retryable", detail)


async def _handle_evidence_collection(db: Session, dispatch) -> HandlerResult:
    from domains.claims.evidence import MAX_EVIDENCE_ATTEMPTS, EvidenceEngine

    from backend.database.models.claim import Claim

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")

    claims = list(db.execute(
        select(Claim).where(Claim.event_id == article.event_id)
    ).scalars().all())
    if not claims:
        return HandlerResult("retryable", "claims not extracted yet")

    pending = [
        c for c in claims
        if not c.evidence_extracted
        and int(c.evidence_attempts or 0) < MAX_EVIDENCE_ATTEMPTS
    ]
    if not pending:
        return HandlerResult(
            "completed", "", meta={"event_id": str(article.event_id),
                                   "claims": len(claims)})

    outcome = await EvidenceEngine(db).run(
        limit=len(pending), claim_ids=[c.id for c in pending])
    recheck = list(db.execute(
        select(Claim).where(Claim.event_id == article.event_id)
    ).scalars().all())
    remaining = [
        c for c in recheck
        if not c.evidence_extracted
        and int(c.evidence_attempts or 0) < MAX_EVIDENCE_ATTEMPTS
    ]
    meta = {
        "event_id": str(article.event_id),
        "claims_processed": outcome.claims_processed,
        "evidence_created": outcome.evidence_created,
    }
    if not remaining:
        return HandlerResult("completed", "", meta=meta)
    if outcome.skipped and not outcome.claims_processed:
        return HandlerResult("terminal", "evidence skipped (mock provenance)")
    return HandlerResult(
        "retryable", outcome.errors[0] if outcome.errors else "evidence pending",
        meta=meta)


async def _handle_domain_routing(db: Session, dispatch) -> HandlerResult:
    """Derive + persist domain routing from the classification signals.

    Deterministic (no AI, no engine call). Until classification is done there
    is nothing to read — retryable, like event_extraction. Completed once the
    routing payload is stored; retrying a completed row never repeats.
    After persisting, ONLY the routed domains in ``DOMAIN_TASKS`` get a
    dispatch row — every relevant article is not sent to every engine.
    """
    from backend.ai.dispatch.routing import DOMAIN_TASKS, persist_domain_routing

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.classification_status != "done":
        return HandlerResult("retryable", "classification not done")

    routing = persist_domain_routing(db, article)
    domain = DispatchService(db)
    for name in routing["domains"]:
        task = DOMAIN_TASKS.get(name)
        if task is not None:
            domain.ensure_dispatch(article.id, task, meta={"domain": name})
    return HandlerResult(
        "completed", "",
        meta={
            "domains": routing["domains"],
            "domain_state": routing["state"],
            "domain_reason_codes": routing["reason_codes"],
            "domain_tasks": [DOMAIN_TASKS[d] for d in routing["domains"]
                             if d in DOMAIN_TASKS],
        })


async def _handle_claim_independence(db: Session, dispatch) -> HandlerResult:
    """Run the real SourceIndependenceEngine for this article's claims.

    Dependencies: event linked + claims extracted (typically after evidence).
    Missing article is terminal, missing upstream is retryable. The engine
    persists through its existing Claim columns; the runner commits.
    """
    from domains.news.independence import SourceIndependenceEngine

    from backend.database.models.claim import Claim

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")

    claims = list(db.execute(
        select(Claim).where(Claim.event_id == article.event_id)
    ).scalars().all())
    if not claims:
        return HandlerResult("retryable", "claims not extracted yet")

    engine = SourceIndependenceEngine(db)
    mapping, _n_sources, _edges = engine.build_groups()
    processed = [engine.analyze_claim(claim, mapping) for claim in claims]
    db.flush()
    return HandlerResult(
        "completed", "",
        meta={
            "event_id": str(article.event_id),
            "claims": len(processed),
            "corroborated": sum(
                1 for p in processed
                if p["verification_status"] == "corroborated"),
        })


async def _handle_domain_geopolitics(db: Session, dispatch) -> HandlerResult:
    """Run the real GeopoliticalEngine for this article's event actors.

    Bounded per-article adapter (Stage93): ``analyze_all(actors=[...])``
    recomputes only this event's actors, each over its FULL per-period
    bucket — engine semantics, upsert idempotency and persistence
    (``GeopoliticalAssessment``) are the engine's own. Upstream: a linked
    event; no actors to analyze completes with explicit empty content.
    """
    from domains.geopolitics.analysis import GeopoliticalEngine

    from backend.database.models.event import Event

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")
    event = db.get(Event, article.event_id)
    if event is None:
        return HandlerResult("retryable", "event row missing")

    try:
        actors = json.loads(event.actors or "[]")
    except (TypeError, ValueError):
        actors = []
    actors = [a for a in actors if isinstance(a, str) and a.strip()]
    if not actors:
        # Empty would mean "no filter" in the engine — never run the
        # unbounded batch from a per-article dispatch.
        return HandlerResult(
            "completed", "no actors; nothing to analyze",
            meta={"event_id": str(event.id), "actors": [],
                  "assessments_stored": 0, "assessments_refreshed": 0})

    outcome = GeopoliticalEngine(db).analyze_all(actors=actors)
    if outcome.failed:
        return HandlerResult(
            "retryable", outcome.errors[0] if outcome.errors else "engine failed",
            meta={"actors": actors})
    return HandlerResult(
        "completed", "",
        meta={
            "event_id": str(event.id),
            "actors": actors,
            "assessments_stored": outcome.stored,
            "assessments_refreshed": outcome.duplicates,
        })


async def _handle_domain_society(db: Session, dispatch) -> HandlerResult:
    """Run the real SocialEngine for this article's scopes.

    Bounded per-article adapter (Stage93): ``analyze_all(scopes=[...])``
    recomputes only this article's (topic, country) scopes, each from ALL of
    that scope's done articles — mood semantics, upsert idempotency and
    persistence (``SocialAssessment``) are the engine's own. Upstream:
    classification signals; no scopes retries (bounded) until reclassified.
    """
    from domains.society.analysis import SocialEngine

    from backend.ai.dispatch.routing import route_article

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.classification_status != "done":
        return HandlerResult("retryable", "classification not done")

    signals = route_article(article)["signals"]
    scopes = [("topic", t) for t in signals["topics"]]
    if signals["country"]:
        scopes.append(("country", signals["country"]))
    if not scopes:
        return HandlerResult("retryable", "no society scope signals")

    outcome = SocialEngine(db).analyze_all(scopes=scopes)
    if outcome.failed:
        return HandlerResult(
            "retryable", outcome.errors[0] if outcome.errors else "engine failed",
            meta={"scopes": [list(s) for s in scopes]})
    return HandlerResult(
        "completed", "",
        meta={
            "scopes": [list(s) for s in scopes],
            "assessments_stored": outcome.stored,
            "assessments_refreshed": outcome.duplicates,
        })


async def _handle_domain_routing_refresh(db: Session, dispatch) -> HandlerResult:
    """Recompute domain routing after event extraction and create missing work.

    Consumes real persisted state (article topics/country + linked event actors
    and event_type). Never infers actors or domains. Creates only the missing
    domain task rows for newly eligible domains; completed domain tasks are
    never repeated merely because routing metadata was recalculated. Honestly
    completes with no new work when nothing changed.
    """
    from backend.ai.dispatch.routing import refresh_domain_routing

    article = _article(db, dispatch.article_id)
    if article is None:
        return HandlerResult("terminal", "article not found")
    if article.classification_status != "done":
        return HandlerResult("retryable", "classification not done")
    if article.event_id is None:
        return HandlerResult("retryable", "event not linked yet")

    result = refresh_domain_routing(db, article, triggered_by_event=article.event_id)
    return HandlerResult(
        "completed", "",
        meta={
            "refresh_changed": result["changed"],
            "domains": result["domains"],
            "domain_state": result["state"],
            "created_tasks": result["created_tasks"],
        })


_HANDLERS = {
    "screening": _handle_screening,
    "domain_routing": _handle_domain_routing,
    "event_extraction": _handle_event_extraction,
    "domain_routing_refresh": _handle_domain_routing_refresh,
    "claim_extraction": _handle_claim_extraction,
    "graph_extraction": _handle_graph_extraction,
    "evidence_collection": _handle_evidence_collection,
    "domain_geopolitics": _handle_domain_geopolitics,
    "domain_society": _handle_domain_society,
    "claim_independence": _handle_claim_independence,
}


# --- runner ------------------------------------------------------------------

async def run_once(
    db: Session,
    *,
    limit: int = 20,
    task: LogicalTask | None = None,
) -> DispatchOutcome:
    """Process due rows once. Safe to call concurrently (atomic claims)."""
    service = DispatchService(db)
    outcome = DispatchOutcome()
    try:
        # Cheap lease recovery on every tick; the full missing-enqueue scan is
        # startup-only (it parses stored decisions).
        service.recover_stale()
    except Exception:  # noqa: BLE001 — recovery must never block new work
        logger.warning("dispatch recovery failed", exc_info=True)
        db.rollback()

    budget = max(1, int(limit))
    for logical in EXECUTABLE_TASKS:
        if task is not None and logical != task:
            continue
        if budget <= 0:
            break
        for dispatch in service.claimable(logical, limit=budget):
            if not service.claim(dispatch):
                continue
            budget -= 1
            outcome.claimed += 1
            bucket = outcome.tasks.setdefault(logical, {})
            try:
                result = await _HANDLERS[logical](db, dispatch)
            except Exception as exc:  # noqa: BLE001 — bounded retry, never crash the loop
                logger.warning("dispatch handler failed | task=%s err=%s",
                               logical, type(exc).__name__)
                result = HandlerResult("retryable", f"{type(exc).__name__}: {exc}")

            if result.status == "completed":
                service.mark_completed(dispatch, result.meta)
                outcome.completed += 1
                bucket["completed"] = bucket.get("completed", 0) + 1
            elif result.status == "terminal":
                service.mark_terminal(dispatch, result.detail or "terminal")
                outcome.terminal += 1
                bucket["terminal"] = bucket.get("terminal", 0) + 1
            else:
                service.mark_retryable(dispatch, result.detail or "retryable")
                outcome.retryable += 1
                bucket["retryable"] = bucket.get("retryable", 0) + 1
            db.commit()
    return outcome


def recover_at_startup(db: Session) -> dict[str, int]:
    """Mark abandoned leases retryable and re-enqueue missing decisions."""
    service = DispatchService(db)
    stale = service.recover_stale()
    missing = service.recover_missing()
    db.commit()
    return {"stale": stale, "reenqueued": missing}


async def run_forever(stop: asyncio.Event, *, interval: int, limit: int) -> None:
    """Bounded background consumer started from the application lifespan."""
    from backend.database.session import get_session_factory

    while not stop.is_set():
        try:
            with get_session_factory()() as db:
                result = await run_once(db, limit=limit)
            if result.claimed:
                logger.info("dispatch tick | %s", result.as_dict())
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a bad DB row must not stop the loop
            logger.warning("dispatch tick failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(1, interval))
        except TimeoutError:
            continue


__all__ = [
    "ANALYSIS_TASKS",
    "DispatchOutcome",
    "HandlerResult",
    "logical_task",
    "recover_at_startup",
    "run_forever",
    "run_once",
]
