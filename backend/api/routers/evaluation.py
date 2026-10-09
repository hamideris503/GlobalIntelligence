"""Forecast Evaluation API (Phase 28).

- POST /api/evaluation/run      → امتیازدهی outcomeهای دارای actual
- GET  /api/evaluation/scores   → امتیاز هر outcome
- GET  /api/evaluation/summary  → تجمیع (MAE/RMSE/Brier/LogLoss/کالیبراسیون)
"""
from __future__ import annotations

from domains.forecast.evaluation import EvaluationEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.session import get_db

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


class EvaluateOutcomeRead(BaseModel):
    scored: int
    skipped: int
    failed: int
    errors: list[str]


class ScoreRead(BaseModel):
    forecast_id: str
    target: str | None
    model: str | None
    expected_value: float | None
    actual_value: float | None
    abs_error: float | None
    squared_error: float | None
    brier_score: float | None
    log_loss: float | None


class SummaryRead(BaseModel):
    n: int
    mae: float | None
    rmse: float | None
    mean_brier: float | None
    mean_log_loss: float | None
    calibration: list[dict]


@router.post("/run", response_model=EvaluateOutcomeRead)
def run_evaluation(
    target: str | None = None, db: Session = Depends(get_db)
) -> EvaluateOutcomeRead:
    """امتیازدهی outcomeها (idempotent؛ بازنویسی همان ردیف)."""
    outcome = EvaluationEngine(db).run(target=target)
    return EvaluateOutcomeRead(**outcome.as_dict())


@router.get("/scores", response_model=list[ScoreRead])
def list_scores(
    target: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ScoreRead]:
    stmt = (
        select(Forecast, ForecastOutcome)
        .join(ForecastOutcome, ForecastOutcome.forecast_id == Forecast.id)
        .order_by(ForecastOutcome.resolved_at.desc())
        .limit(limit)
    )
    if target:
        stmt = stmt.where(Forecast.target == target)
    return [
        ScoreRead(
            forecast_id=str(fc.id),
            target=fc.target,
            model=fc.model,
            expected_value=fc.expected_value,
            actual_value=oc.actual_value,
            abs_error=oc.abs_error,
            squared_error=oc.squared_error,
            brier_score=oc.brier_score,
            log_loss=oc.log_loss,
        )
        for fc, oc in db.execute(stmt).all()
    ]


@router.get("/summary", response_model=SummaryRead)
def summary(
    target: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
) -> SummaryRead:
    """تجمیع live امتیازها + جدول کالیبراسیون."""
    return SummaryRead(**EvaluationEngine(db).summary(target=target, model=model))
