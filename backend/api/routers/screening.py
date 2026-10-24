"""Screening orchestration + operational review queue (Stage88/91).

Thin HTTP surface over the central policy so the four Kev/Laya enablement
combinations can be exercised without touching historical artifacts. The queue
is derived from persisted outcomes; an acknowledgement is additive and never
rewrites the automated decision.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai.local_screening import orchestrator as orch
from backend.ai.local_screening import review
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
    screening_status: str
    review_required: bool
    review_reasons: list[str]
    review_acknowledged: bool
    acknowledged_at: str | None = None


class ReviewPageRead(BaseModel):
    items: list[ReviewItemRead]
    page: int
    page_size: int
    has_more: bool


class AckRequest(BaseModel):
    note: str | None = Field(default=None, max_length=review.MAX_NOTE)


class AckRead(ReviewItemRead):
    already_acknowledged: bool
    human_review: dict


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
    return ReviewPageRead(**review.queue_page(
        db,
        page=page,
        page_size=page_size,
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
