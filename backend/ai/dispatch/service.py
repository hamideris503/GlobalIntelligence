"""ArticleDispatch service — durable downstream dispatch tracking (Stage89).

Design notes
------------
* Idempotency key: ``(article_id, task_name)`` where ``task_name`` is
  ``"<logical_task>@v<analysis_version>"``. The version is part of the stored
  key, so a handler version bump creates a new row instead of silently
  re-using a completed one; no schema migration is required and the existing
  unique constraint remains the concurrency guard.
* Enqueue happens in the caller's transaction. The classifier commits the
  classification result, the screening provenance and these rows together, so
  a crash cannot persist a decision without its dispatch.
* Claims are atomic ``UPDATE ... WHERE status IN (...)`` statements (the same
  pattern as ``source_bot.jobs.claim_job``), so two processes cannot both run
  one row. Postgres and the test SQLite both honour rowcount.
* Retries are bounded (default 3) with exponential backoff; permanent errors
  become ``terminal`` and never loop.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article_dispatch import ArticleDispatch

logger = get_logger(__name__)

LogicalTask = Literal[
    "classification",
    "screening",
    "domain_routing",
    "event_extraction",
    "domain_routing_refresh",
    "claim_extraction",
    "graph_extraction",
    "evidence_collection",
    "domain_geopolitics",
    "domain_society",
    "claim_independence",
]
DispatchStatus = Literal["pending", "running", "completed", "retryable", "terminal"]

# Handlers are versioned independently of the stored rows. Only a real change
# in a task's semantics should bump this constant.
ANALYSIS_VERSION = "1"

# Dependency order. `classification` is a bookkeeping row written by the
# classifier itself and is never executed by the dispatcher.
# `domain_routing` runs FIRST among analysis tasks: it derives domains from
# the persisted classification signals and records (in
# classification_meta["domain_routing"]) which engines apply, then enqueues
# ONLY the domain rows whose domain is routed (DOMAIN_TASKS). It fans out to
# no engine by itself — the matrix decides what is actually connected.
# `domain_geopolitics`/`domain_society` (Stage93) run after extraction so the
# event's actors / the article's default scopes exist.
# `domain_routing_refresh` (Stage94) runs after event_extraction: once the
# event's actors/event_type are persisted, routing is recomputed and any newly
# eligible domain task is created. It is never produced by screening enqueue.
# `claim_independence` runs LAST: it needs claims and their evidence.
TASK_ORDER: tuple[LogicalTask, ...] = (
    "classification",
    "screening",
    "domain_routing",
    "event_extraction",
    "domain_routing_refresh",
    "claim_extraction",
    "graph_extraction",
    "evidence_collection",
    "domain_geopolitics",
    "domain_society",
    "claim_independence",
)
EXECUTABLE_TASKS: tuple[LogicalTask, ...] = (
    "screening",
    "domain_routing",
    "event_extraction",
    "domain_routing_refresh",
    "claim_extraction",
    "graph_extraction",
    "evidence_collection",
    "domain_geopolitics",
    "domain_society",
    "claim_independence",
)
# Tasks that only make sense once an Article exists and passed screening.
ANALYSIS_TASKS: tuple[LogicalTask, ...] = (
    "domain_routing",
    "event_extraction",
    "claim_extraction",
    "graph_extraction",
    "evidence_collection",
    "claim_independence",
)

_MAX_ERROR = 500


def utcnow() -> datetime:
    return datetime.now(UTC)


def task_key(task: LogicalTask | str) -> str:
    """Stored task name: logical task + analysis version (fits String(32))."""
    return f"{task}@v{ANALYSIS_VERSION}"


def logical_task(stored: str) -> str:
    return (stored or "").split("@", 1)[0]


def _merge_meta(raw: str | None, extra: dict[str, Any] | None) -> str | None:
    if not extra:
        return raw
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.update(extra)
    return json.dumps(data, ensure_ascii=False)


def _sanitize(error: str) -> str:
    line = " ".join(str(error).split())
    return line[:_MAX_ERROR]


class DispatchService:
    """Durable, idempotent per-article task queue."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    # --- enqueue ---------------------------------------------------------
    def ensure_dispatch(
        self,
        article_id: uuid.UUID,
        task: LogicalTask | str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> ArticleDispatch:
        """Return the existing row or create it; never duplicates a target."""
        key = task_key(task)
        existing = self.db.execute(
            select(ArticleDispatch).where(
                ArticleDispatch.article_id == article_id,
                ArticleDispatch.task_name == key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.meta = _merge_meta(existing.meta, meta)
            self.db.flush()
            return existing

        dispatch = ArticleDispatch(
            article_id=article_id,
            task_name=key,
            status="pending",
            attempts=0,
            meta=json.dumps(meta or {}, ensure_ascii=False),
        )
        try:
            # Savepoint: a concurrent enqueue may win the unique constraint and
            # must not poison the caller's transaction.
            with self.db.begin_nested():
                self.db.add(dispatch)
                self.db.flush()
        except IntegrityError:
            winner = self.db.execute(
                select(ArticleDispatch).where(
                    ArticleDispatch.article_id == article_id,
                    ArticleDispatch.task_name == key,
                )
            ).scalar_one_or_none()
            if winner is None:  # pragma: no cover - defensive
                raise
            winner.meta = _merge_meta(winner.meta, meta)
            self.db.flush()
            return winner
        return dispatch

    def enqueue_after_screening(
        self,
        article_id: uuid.UUID,
        decision: Any,
    ) -> list[ArticleDispatch]:
        """Translate one screening decision into durable work.

        - relevant=True  -> both sides of the pipeline get analysis tasks.
        - relevant=None  -> a durable `screening` retry row (never "irrelevant").
        - relevant=False -> no ordinary analysis dispatch; the article and the
          screening provenance stay in place. A P0/P1 safeguard outcome is
          persisted as ``p0_p1_safeguard``/``PRIORITY_REVIEW`` in the article's
          stored screening metadata (served by ``GET /api/dispatch/articles``),
          never as a fake analysis job.
        """
        provenance = {
            "screening_route": getattr(decision, "route", None),
            "screening_decision": getattr(decision, "relevant", None),
            "screening_reason_codes": list(getattr(decision, "reason_codes", []) or []),
            "p0_p1_safeguard": bool(getattr(decision, "p0_p1_safeguard", False)),
            "scope_rule_version": (
                decision.as_dict().get("scope_rule_version")
                if hasattr(decision, "as_dict") else None
            ),
        }
        rows: list[ArticleDispatch] = []
        if getattr(decision, "relevant", None) is True:
            for task in ANALYSIS_TASKS:
                rows.append(self.ensure_dispatch(article_id, task, meta=provenance))
            return rows
        if getattr(decision, "relevant", None) is None:
            provenance["durable_state"] = "screening_pending"
            rows.append(self.ensure_dispatch(article_id, "screening", meta=provenance))
            return rows
        return rows

    # --- claim / state transitions --------------------------------------
    def claim(self, dispatch: ArticleDispatch) -> bool:
        """Atomically move one due row to running; False means someone else owns it."""
        now = utcnow()
        res = self.db.execute(
            update(ArticleDispatch)
            .where(
                ArticleDispatch.id == dispatch.id,
                ArticleDispatch.status.in_(("pending", "retryable")),
                or_(
                    ArticleDispatch.next_retry_at.is_(None),
                    ArticleDispatch.next_retry_at <= now,
                ),
            )
            .values(
                status="running",
                attempts=ArticleDispatch.attempts + 1,
                last_error=None,
            )
        )
        self.db.flush()
        if (res.rowcount or 0) != 1:
            return False
        self.db.refresh(dispatch)
        return True

    def mark_completed(
        self, dispatch: ArticleDispatch, meta: dict[str, Any] | None = None,
    ) -> None:
        dispatch.status = "completed"
        dispatch.next_retry_at = None
        dispatch.last_error = None
        dispatch.meta = _merge_meta(dispatch.meta, meta)
        self.db.flush()

    def mark_retryable(self, dispatch: ArticleDispatch, error: str) -> None:
        attempts = int(dispatch.attempts or 0)
        max_attempts = max(1, int(self.settings.dispatch_max_attempts))
        if attempts >= max_attempts:
            self.mark_terminal(dispatch, f"max attempts reached: {error}")
            return
        delay = min(30 * (2 ** max(0, attempts - 1)), 600)
        dispatch.status = "retryable"
        dispatch.last_error = _sanitize(error)
        dispatch.next_retry_at = utcnow() + timedelta(seconds=delay)
        self.db.flush()

    def mark_terminal(self, dispatch: ArticleDispatch, error: str) -> None:
        dispatch.status = "terminal"
        dispatch.last_error = _sanitize(error)
        dispatch.next_retry_at = None
        self.db.flush()

    # --- recovery --------------------------------------------------------
    def recover_stale(self, *, stale_seconds: int | None = None) -> int:
        """Return rows abandoned mid-run to retryable without losing the work."""
        seconds = (
            int(self.settings.dispatch_lease_seconds)
            if stale_seconds is None else stale_seconds
        )
        cutoff = utcnow() - timedelta(seconds=max(1, seconds))
        rows = list(self.db.execute(
            select(ArticleDispatch).where(
                ArticleDispatch.status == "running",
                ArticleDispatch.updated_at < cutoff,
            )
        ).scalars().all())
        max_attempts = max(1, int(self.settings.dispatch_max_attempts))
        for row in rows:
            if int(row.attempts or 0) >= max_attempts:
                row.status = "terminal"
                row.next_retry_at = None
                row.last_error = "stale running recovered; max attempts reached"
                continue
            row.status = "retryable"
            row.next_retry_at = utcnow()
            row.last_error = "stale running recovered after restart"
        self.db.flush()
        if rows:
            logger.warning("dispatch stale running recovered | n=%s", len(rows))
        return len(rows)

    def recover_missing(self, *, lookback: int = 500) -> int:
        """Re-enqueue articles whose stored screening decision has no rows.

        Covers a crash between the classification commit and any older writer
        that committed the decision without dispatch, and rows created before
        task versioning. Bounded and read-only apart from the idempotent
        enqueue itself.
        """
        from backend.database.models.article import Article

        articles = list(self.db.execute(
            select(Article)
            .where(Article.classification_status == "done")
            .order_by(Article.retrieved_at.desc().nullslast())
            .limit(lookback)
        ).scalars().all())
        created = 0
        for article in articles:
            try:
                meta = json.loads(article.classification_meta or "{}")
            except (TypeError, ValueError):
                continue
            screening = (meta.get("local_screening") or {}) if isinstance(meta, dict) else {}
            if not isinstance(screening, dict):
                continue
            decision = screening.get("decision")
            expected = (ANALYSIS_TASKS if decision is True
                        else ("screening",) if decision is None else ())
            # Stage93: connected domain tasks are re-derived from the persisted
            # routing so a crash between the routing enqueue and its commit is
            # recovered — only domains the routing actually assigned.
            if decision is True:
                routing = meta.get("domain_routing")
                if isinstance(routing, dict):
                    from backend.ai.dispatch.routing import DOMAIN_TASKS
                    for domain in routing.get("domains") or []:
                        task = DOMAIN_TASKS.get(domain)
                        if task:
                            expected = expected + (task,)
            for task in expected:
                exists = self.db.execute(
                    select(ArticleDispatch.id).where(
                        ArticleDispatch.article_id == article.id,
                        ArticleDispatch.task_name == task_key(task),
                    )
                ).first()
                if exists is None:
                    self.ensure_dispatch(
                        article.id, task,
                        meta={
                            "screening_route": screening.get("route"),
                            "screening_decision": decision,
                            "recovered": True,
                        },
                    )
                    created += 1
        self.db.flush()
        if created:
            logger.warning("dispatch rows recovered from stored decisions | n=%s", created)
        return created

    # --- queries ---------------------------------------------------------
    def claimable(
        self, task: LogicalTask, *, limit: int = 20,
    ) -> list[ArticleDispatch]:
        now = utcnow()
        stmt = (
            select(ArticleDispatch)
            .where(
                ArticleDispatch.task_name == task_key(task),
                ArticleDispatch.status.in_(("pending", "retryable")),
                or_(
                    ArticleDispatch.next_retry_at.is_(None),
                    ArticleDispatch.next_retry_at <= now,
                ),
            )
            .order_by(ArticleDispatch.created_at)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_dispatch(
        self, article_id: uuid.UUID, task: LogicalTask | str,
    ) -> ArticleDispatch | None:
        return self.db.execute(
            select(ArticleDispatch).where(
                ArticleDispatch.article_id == article_id,
                ArticleDispatch.task_name == task_key(task),
            )
        ).scalar_one_or_none()

    def for_article(self, article_id: uuid.UUID) -> list[ArticleDispatch]:
        return list(self.db.execute(
            select(ArticleDispatch)
            .where(ArticleDispatch.article_id == article_id)
            .order_by(ArticleDispatch.task_name)
        ).scalars().all())

    def status_summary(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(
                ArticleDispatch.task_name,
                ArticleDispatch.status,
                func.count(),
            ).group_by(ArticleDispatch.task_name, ArticleDispatch.status)
        ).all()
        counts: dict[str, dict[str, int]] = {}
        for stored, status, count in rows:
            task = logical_task(stored)
            counts.setdefault(task, {})[status] = int(count)
        recent_failures = list(self.db.execute(
            select(ArticleDispatch)
            .where(ArticleDispatch.status.in_(("retryable", "terminal")))
            .order_by(ArticleDispatch.updated_at.desc())
            .limit(10)
        ).scalars().all())
        return {
            "analysis_version": ANALYSIS_VERSION,
            "tasks": counts,
            "recent_failures": [
                {
                    "article_id": str(row.article_id),
                    "task": logical_task(row.task_name),
                    "status": row.status,
                    "attempts": row.attempts,
                    "last_error": row.last_error,
                    "next_retry_at": (
                        row.next_retry_at.isoformat() if row.next_retry_at else None
                    ),
                }
                for row in recent_failures
            ],
        }
