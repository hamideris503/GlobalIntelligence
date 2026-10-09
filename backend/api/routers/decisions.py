"""Decision Engine API (Phase 32).

- POST /api/decisions/run → تصمیم قانون‌مند برای اهداف (افزودنی)
- GET  /api/decisions       → لیست تصمیم‌ها (فیلتر دارایی)
- GET  /api/decisions/{id}  → یک تصمیم
"""
from __future__ import annotations

import uuid

from domains.decision.engine import DecisionEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.recommendation import Recommendation
from backend.database.session import get_db

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class DecideOutcomeRead(BaseModel):
    decided: int
    skipped: int
    failed: int
    decision_ids: list[str]
    errors: list[str]


class DecisionRead(BaseModel):
    id: str
    asset: str
    direction: str | None
    horizon: str | None
    decision: str | None
    score: float | None
    confidence: float | None
    expected_return: float | None
    downside: float | None
    main_drivers: str | None
    main_risks: str | None
    invalidation: str | None
    model: str | None
    rank: int | None


def _to_decision(r: Recommendation) -> DecisionRead:
    return DecisionRead(
        id=str(r.id),
        asset=r.asset,
        direction=r.direction,
        horizon=r.horizon,
        decision=r.decision,
        score=r.score,
        confidence=r.confidence,
        expected_return=r.expected_return,
        downside=r.downside,
        main_drivers=r.main_drivers,
        main_risks=r.main_risks,
        invalidation=r.invalidation,
        model=r.model,
        rank=r.rank,
    )


@router.post("/run", response_model=DecideOutcomeRead)
def run_decisions(
    targets: list[str] | None = Query(default=None),
    horizon: str = Query(default="short"),
    db: Session = Depends(get_db),
) -> DecideOutcomeRead:
    """تصمیم قانون‌مند برای اهداف (پیش‌فرض: همه‌ی اهداف دارای سناریو)."""
    outcome = DecisionEngine(db).run(targets=targets, horizon=horizon)
    return DecideOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[DecisionRead])
def list_decisions(
    asset: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[DecisionRead]:
    stmt = (
        select(Recommendation)
        .order_by(Recommendation.created_at.desc())
        .limit(limit)
    )
    if asset:
        stmt = stmt.where(Recommendation.asset == asset)
    return [_to_decision(r) for r in db.execute(stmt).scalars().all()]


@router.get("/{decision_id}", response_model=DecisionRead)
def get_decision(
    decision_id: uuid.UUID, db: Session = Depends(get_db)
) -> DecisionRead:
    decision = db.get(Recommendation, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return _to_decision(decision)
