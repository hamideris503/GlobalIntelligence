"""Model Performance API (Phase 36).

- POST /api/performance/record → ثبت عملکرد دوره‌ای مدل‌ها
- GET  /api/performance          → leaderboard (آخرین دوره‌ی هر مدل)
- GET  /api/performance/history  → تاریخچه‌ی یک مدل
"""
from __future__ import annotations

from domains.forecast.performance import PerformanceEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.model_performance import ModelPerformance
from backend.database.session import get_db

router = APIRouter(prefix="/api/performance", tags=["performance"])


class PerformanceOutcomeRead(BaseModel):
    models_recorded: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class PerformanceRead(BaseModel):
    model: str
    period: str
    n_scored: int | None
    mae: float | None
    rmse: float | None
    mean_brier: float | None
    mean_log_loss: float | None
    method: str | None


def _to_perf(p: ModelPerformance) -> PerformanceRead:
    return PerformanceRead(
        model=p.model,
        period=p.period,
        n_scored=p.n_scored,
        mae=p.mae,
        rmse=p.rmse,
        mean_brier=p.mean_brier,
        mean_log_loss=p.mean_log_loss,
        method=p.method,
    )


def _sort_key(p: PerformanceRead) -> tuple:
    if p.mae is not None:
        return (0, p.mae)
    if p.mean_brier is not None:
        return (1, p.mean_brier)
    return (2, 0.0)


@router.post("/record", response_model=PerformanceOutcomeRead)
def record_performance(
    period: str | None = None, db: Session = Depends(get_db)
) -> PerformanceOutcomeRead:
    """ثبت عملکرد دوره‌ای همه‌ی مدل‌های دارای outcome (idempotent)."""
    outcome = PerformanceEngine(db).record(period=period)
    return PerformanceOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[PerformanceRead])
def leaderboard(db: Session = Depends(get_db)) -> list[PerformanceRead]:
    """آخرین رکورد هر مدل، مرتب به‌ترتیب دقت (MAE سپس Brier)."""
    stmt = select(ModelPerformance).order_by(
        ModelPerformance.model, ModelPerformance.period.desc()
    )
    seen: set[str] = set()
    out: list[PerformanceRead] = []
    for p in db.execute(stmt).scalars().all():
        if p.model in seen:
            continue
        seen.add(p.model)
        out.append(_to_perf(p))
    out.sort(key=_sort_key)
    return out


@router.get("/history", response_model=list[PerformanceRead])
def history(
    model: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PerformanceRead]:
    stmt = (
        select(ModelPerformance)
        .where(ModelPerformance.model == model)
        .order_by(ModelPerformance.period.desc())
        .limit(limit)
    )
    return [_to_perf(p) for p in db.execute(stmt).scalars().all()]
