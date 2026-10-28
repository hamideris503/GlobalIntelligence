"""Dispatch status, manual trigger and operational job list (Stage89/91).

Screening status and dispatch status are reported separately: a row existing
never means "analysis complete"; only ``status == "completed"`` does. A manual
retry can only make an already-``retryable`` row due again; it never resets
attempts, never duplicates a row and never re-runs completed work.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.ai.dispatch.runner import run_once
from backend.ai.dispatch.service import DispatchService, logical_task
from backend.ai.local_screening import review
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document
from backend.database.session import get_db

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])

JobStatus = Literal["pending", "running", "completed", "retryable", "terminal"]
JobTask = Literal[
    "classification", "screening", "domain_routing", "event_extraction",
    "domain_routing_refresh", "claim_extraction", "graph_extraction",
    "evidence_collection", "domain_geopolitics", "domain_society",
    "claim_independence",
]


class DispatchRead(BaseModel):
    task: str
    status: str
    attempts: int
    last_error: str | None = None
    next_retry_at: str | None = None


class DispatchRunRead(BaseModel):
    claimed: int
    completed: int
    retryable: int
    terminal: int
    tasks: dict[str, dict[str, int]]


class ArticleDispatchRead(BaseModel):
    article_id: str
    screening: dict | None = None
    domains: dict | None = None
    dispatches: list[DispatchRead]


class DispatchJobRead(BaseModel):
    dispatch_id: str
    article_id: str
    title: str | None = None
    article_url: str | None = None
    priority: str | None = None
    task: str
    task_version: str
    status: str
    attempts: int
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    next_retry_at: str | None = None
    can_retry: bool
    screening: dict | None = None
    screening_status: str
    review_required: bool
    review_reasons: list[str]
    review_acknowledged: bool


class DispatchJobPageRead(BaseModel):
    items: list[DispatchJobRead]
    page: int
    page_size: int
    has_more: bool


def _screening_meta(article: Article | None) -> dict | None:
    if article is None:
        return None
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    screening = meta.get("local_screening")
    return screening if isinstance(screening, dict) else None


def _domains_meta(article: Article | None) -> dict | None:
    if article is None:
        return None
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    routing = meta.get("domain_routing")
    return routing if isinstance(routing, dict) else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _version(stored: str) -> str:
    return stored.rsplit("@v", 1)[1] if "@v" in stored else ""


def _job(row: ArticleDispatch, article: Article, document: Document | None) -> DispatchJobRead:
    meta = review.parse_meta(article.classification_meta)
    state = review.review_state(meta, article.classification_status)
    return DispatchJobRead(
        dispatch_id=str(row.id),
        article_id=str(article.id),
        title=article.title or (document.title if document else None),
        article_url=(document.url or document.canonical_url) if document else None,
        priority=document.ingestion_priority if document else None,
        task=logical_task(row.task_name),
        task_version=_version(row.task_name),
        status=row.status,
        attempts=row.attempts,
        last_error=row.last_error,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        next_retry_at=_iso(row.next_retry_at),
        can_retry=row.status == "retryable",
        screening=review.screening_meta(meta),
        screening_status=state["screening_status"],
        review_required=state["review_required"],
        review_reasons=state["review_reasons"],
        review_acknowledged=state["review_acknowledged"],
    )


@router.get("/status")
def dispatch_status(db: Session = Depends(get_db)) -> dict:
    return DispatchService(db).status_summary()


@router.get("/jobs", response_model=DispatchJobPageRead)
def dispatch_jobs(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=100),
    status: JobStatus | None = Query(default=None),
    task: JobTask | None = Query(default=None),
    review_required: bool | None = Query(default=None),
    p0_p1: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DispatchJobPageRead:
    """Bounded page of real ``article_dispatches`` rows joined to their article."""
    stmt = (
        select(ArticleDispatch, Article, Document)
        .join(Article, ArticleDispatch.article_id == Article.id)
        .outerjoin(Document, Article.document_id == Document.id)
    )
    if status is not None:
        stmt = stmt.where(ArticleDispatch.status == status)
    if task is not None:
        stmt = stmt.where(ArticleDispatch.task_name.like(f"{task}@v%"))
    if review_required is not None:
        stmt = stmt.where(
            review.review_clause() if review_required else ~review.review_clause()
        )
    if p0_p1:
        stmt = stmt.where(func.upper(Document.ingestion_priority).in_(("P0", "P1")))

    rows = db.execute(
        stmt.order_by(
            ArticleDispatch.created_at.desc(), ArticleDispatch.id.desc()
        ).limit(page_size + 1).offset((page - 1) * page_size)
    ).all()
    has_more = len(rows) > page_size
    return DispatchJobPageRead(
        items=[_job(row, article, document) for row, article, document in rows[:page_size]],
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.post("/{dispatch_id}/retry", response_model=DispatchJobRead)
def retry_dispatch(
    dispatch_id: uuid.UUID, db: Session = Depends(get_db),
) -> DispatchJobRead:
    """Make a ``retryable`` row due now via the existing claim mechanism.

    - ``pending`` is already claimable: no-op, idempotent.
    - ``retryable`` gets ``next_retry_at = now``; attempts are untouched.
    - ``running``/``completed``/``terminal`` are refused: no duplicate work and
      no terminal row presented as success or silently re-run.
    """
    row = db.get(ArticleDispatch, dispatch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="dispatch not found")
    if row.status == "pending":
        article, document = _joined(db, row)
        return _job(row, article, document)
    if row.status != "retryable":
        raise HTTPException(
            status_code=409,
            detail=f"dispatch is {row.status}; only retryable rows can be retried",
        )

    result = db.execute(
        update(ArticleDispatch)
        .where(
            ArticleDispatch.id == dispatch_id,
            ArticleDispatch.status == "retryable",
        )
        .values(next_retry_at=datetime.now(UTC))
    )
    db.commit()
    if (result.rowcount or 0) != 1:
        raise HTTPException(
            status_code=409,
            detail="dispatch changed concurrently; refresh before retrying",
        )
    db.refresh(row)
    article, document = _joined(db, row)
    return _job(row, article, document)


def _joined(db: Session, row: ArticleDispatch) -> tuple[Article, Document | None]:
    article = db.get(Article, row.article_id)
    if article is None:  # FK cascades, so this is defensive only
        raise HTTPException(status_code=404, detail="article not found")
    document = db.get(Document, article.document_id) if article.document_id else None
    return article, document


@router.post("/run", response_model=DispatchRunRead)
async def run_dispatch(
    limit: int = Query(default=20, ge=1, le=200),
    task: Literal[
        "screening", "domain_routing", "event_extraction",
        "domain_routing_refresh", "claim_extraction", "graph_extraction",
        "evidence_collection", "domain_geopolitics", "domain_society",
        "claim_independence",
    ] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DispatchRunRead:
    outcome = await run_once(db, limit=limit, task=task)
    return DispatchRunRead(**outcome.as_dict())


@router.get("/articles/{article_id}", response_model=ArticleDispatchRead)
def article_dispatch(article_id: uuid.UUID, db: Session = Depends(get_db)) -> ArticleDispatchRead:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    rows = DispatchService(db).for_article(article_id)
    return ArticleDispatchRead(
        article_id=str(article_id),
        screening=_screening_meta(article),
        domains=_domains_meta(article),
        dispatches=[
            DispatchRead(
                task=logical_task(row.task_name),
                status=row.status,
                attempts=row.attempts,
                last_error=row.last_error,
                next_retry_at=(
                    row.next_retry_at.isoformat() if row.next_retry_at else None
                ),
            )
            for row in rows
        ],
    )
