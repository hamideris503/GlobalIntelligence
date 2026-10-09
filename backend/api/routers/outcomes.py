"""Outcome Engine API (Phase 27).

- POST /api/outcomes/resolve  → تطبیق نتایج واقعی به پیش‌بینی‌های سررسیده
- GET  /api/outcomes           → لیست outcomeها (فیلتر هدف)
- GET  /api/outcomes/pending   → پیش‌بینی‌های سررسیده‌ی بدون outcome
"""
from __future__ import annotations

from domains.forecast.outcome import OutcomeEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.session import get_db

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


class ResolveOutcomeRead(BaseModel):
    resolved: int
    skipped: int
    failed: int
    errors: list[str]


class OutcomeRead(BaseModel):
    forecast_id: str
    target: str | None
    expected_value: float | None
    actual_value: float | None
    resolved_at: str | None
    brier_score: float | None
    abs_error: float | None


class PendingRead(BaseModel):
    forecast_id: str
    target: str
    target_date: str | None
    status: str


def _to_outcome(fc: Forecast, oc: ForecastOutcome) -> OutcomeRead:
    return OutcomeRead(
        forecast_id=str(fc.id),
        target=fc.target,
        expected_value=fc.expected_value,
        actual_value=oc.actual_value,
        resolved_at=oc.resolved_at.isoformat() if oc.resolved_at else None,
        brier_score=oc.brier_score,
        abs_error=oc.abs_error,
    )


@router.post("/resolve", response_model=ResolveOutcomeRead)
def resolve_outcomes(
    target: str | None = None, db: Session = Depends(get_db)
) -> ResolveOutcomeRead:
    """تطبیق نتایج واقعی به پیش‌بینی‌های سررسیده (idempotent)."""
    outcome = OutcomeEngine(db).resolve_all(target=target)
    return ResolveOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[OutcomeRead])
def list_outcomes(
    target: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[OutcomeRead]:
    stmt = (
        select(Forecast, ForecastOutcome)
        .join(ForecastOutcome, ForecastOutcome.forecast_id == Forecast.id)
        .order_by(ForecastOutcome.resolved_at.desc())
        .limit(limit)
    )
    if target:
        stmt = stmt.where(Forecast.target == target)
    return [_to_outcome(fc, oc) for fc, oc in db.execute(stmt).all()]


@router.get("/pending", response_model=list[PendingRead])
def list_pending(db: Session = Depends(get_db)) -> list[PendingRead]:
    rows = OutcomeEngine(db).pending()
    return [
        PendingRead(
            forecast_id=str(fc.id),
            target=fc.target or "",
            target_date=fc.target_date.isoformat() if fc.target_date else None,
            status=fc.status,
        )
        for fc in rows
    ]
