"""Screening orchestration + operational review queue (Stage88/91).

Thin HTTP surface over the central policy so the four Kev/Laya enablement
combinations can be exercised without touching historical artifacts. The queue
is derived from persisted outcomes; an acknowledgement is additive and never
rewrites the automated decision.
"""
from __future__ import annotations

import uuid
from typing import Literal

from domains.inbox import decisions
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai.local_screening import orchestrator as orch
from backend.ai.local_screening import review
from backend.api.pagination import page_params
from backend.auth.deps import CurrentUser, require_user
from backend.database.session import get_db

router = APIRouter(prefix="/api/screening", tags=["screening"])

ScreeningFilter = Literal[
    "missing", "skipped", "pending", "failed", "relevant", "not_relevant"
]


class ScreenRequest(BaseModel):
    text: str
    priority: str | None = None


class ReviewItemRead(BaseModel):
    article_id: str
    title: str | None = None
    article_url: str | None = None
    source_name: str | None = None
    priority: str | None = None
    priority_source: str | None = None
    classification_status: str | None = None
    classification_error: str | None = None
    retrieved_at: str | None = None
    screening: dict | None = None
    domains: list[str] | None = None
    domain_state: str | None = None
    screening_status: str
    review_required: bool
    review_reasons: list[str]
    review_acknowledged: bool
    acknowledged_at: str | None = None


class ReviewPageRead(BaseModel):
    items: list[ReviewItemRead]
    total: int
    page: int
    page_size: int
    has_more: bool


class AckRequest(BaseModel):
    note: str | None = Field(default=None, max_length=review.MAX_NOTE)


class AckRead(ReviewItemRead):
    already_acknowledged: bool
    human_review: dict


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_evidence", "ack"]
    note: str | None = Field(default=None, max_length=decisions.MAX_NOTE)


@router.post("/screen")
async def screen(req: ScreenRequest, db=Depends(get_db)) -> dict:
    decision = await orch.screen_with_db(db, req.text, req.priority)
    return decision.as_dict()


@router.get("/queue", response_model=ReviewPageRead)
def review_queue(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=review.MAX_PAGE_SIZE),
    review_required: bool = Query(default=True),
    p0_p1: bool = Query(default=False),
    acknowledged: bool | None = Query(default=None),
    screening: ScreeningFilter | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewPageRead:
    """Bounded page of the review queue (default) or of the other outcomes."""
    params = page_params(page=page, page_size=page_size, max_size=review.MAX_PAGE_SIZE)
    return ReviewPageRead(**review.queue_page(
        db,
        page=params.page,
        page_size=params.page_size,
        review_required=review_required,
        p0_p1=p0_p1,
        acknowledged=acknowledged,
        screening=screening,
    ))


@router.post("/review/{article_id}/ack", response_model=AckRead)
def acknowledge_review(
    article_id: uuid.UUID,
    req: AckRequest | None = None,
    db: Session = Depends(get_db),
) -> AckRead:
    try:
        return AckRead(**review.acknowledge(
            db, article_id, note=req.note if req else None))
    except review.ReviewNotFound:
        raise HTTPException(status_code=404, detail="article not found") from None
    except review.ReviewConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/review/{article_id}/decision")
def record_review_decision(
    article_id: uuid.UUID,
    req: DecisionRequest,
    current: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    """ثبت تصمیم انسانی در `human_reviews` (تحلیل‌گر به بالا).

    خروجی ماشین بازنویسی نمی‌شود؛ تصمیم فقط append می‌شود.
    """
    try:
        entry = decisions.record_decision(
            db, article_id, action=req.decision,
            actor=current.username, actor_user_id=current.session_id,
            note=req.note,
        )
    except decisions.ReviewEntityNotFound:
        raise HTTPException(status_code=404, detail="article not found") from None
    except decisions.ReviewActionInvalid as exc:
        raise HTTPException(status_code=422, detail=f"invalid decision: {exc}") from None
    return {"decision": entry, "history": decisions.history(db, article_id)}


@router.get("/summary")
def screening_summary(db: Session = Depends(get_db)) -> dict:
    """KPIهای غربالگری با تعریف صریح هر عدد."""
    from sqlalchemy import func, select

    from backend.database.models.article import Article

    total = int(db.execute(select(func.count()).select_from(Article)).scalar_one() or 0)
    queue = int(
        db.execute(
            select(func.count()).select_from(Article).where(review.review_clause())
        ).scalar_one() or 0
    )
    relevant = int(
        db.execute(
            select(func.count()).select_from(Article)
            .where(review._contains('"decision": true'))
        ).scalar_one() or 0
    )
    not_relevant = int(
        db.execute(
            select(func.count()).select_from(Article)
            .where(review._contains('"decision": false'))
        ).scalar_one() or 0
    )
    pending = int(
        db.execute(
            select(func.count()).select_from(Article)
            .where(review._contains('"decision": null'))
        ).scalar_one() or 0
    )
    decided = relevant + not_relevant
    relevant_pct = round(relevant * 100 / decided, 1) if decided else None
    uncertain_pct = round(pending * 100 / total, 1) if total else None

    runtime: dict | None = None
    try:
        from backend.ai.local_runtimes.supervisor import get_supervisor

        runtime = get_supervisor().all_status()
    except Exception:  # noqa: BLE001
        runtime = None

    return {
        "queue_total": queue,
        "relevant": relevant,
        "not_relevant": not_relevant,
        "pending": pending,
        "relevant_pct": relevant_pct,
        "uncertain_pct": uncertain_pct,
        "runtime": runtime,
        "definitions": {
            "queue_total": "articles requiring human review",
            "relevant_pct": "relevant / (relevant + not_relevant); null if no decision yet",
            "uncertain_pct": "pending / total articles; null if no articles",
            "runtime": "Kev/Laya supervisor status (enabled/loaded)",
        },
    }
