"""Forecast Engine API (Phase 25).

- POST /api/forecasts/run  → اجرای baseline و ثبت در Ledger (افزودنی)
- GET  /api/forecasts       → لیست پیش‌بینی‌ها (فیلتر هدف/مدل)
- GET  /api/forecasts/{id}  → یک پیش‌بینی
"""
from __future__ import annotations

import uuid
from datetime import datetime

from domains.forecast.engine import ForecastEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.forecast import Forecast
from backend.database.session import get_db

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


class ForecastOutcomeRead(BaseModel):
    created: int
    skipped: int
    failed: int
    superseded: int
    forecast_ids: list[str]
    errors: list[str]


class ForecastRead(BaseModel):
    id: str
    target: str
    horizon: str | None
    target_date: str | None
    expected_value: float | None
    interval_low: float | None
    interval_high: float | None
    confidence: float | None
    model: str | None
    model_version: str | None
    scenario: str | None
    status: str
    data_version: str | None
    valid_from: str | None


def _to_forecast(f: Forecast) -> ForecastRead:
    return ForecastRead(
        id=str(f.id),
        target=f.target,
        horizon=f.horizon,
        target_date=f.target_date.isoformat() if f.target_date else None,
        expected_value=f.expected_value,
        interval_low=f.interval_low,
        interval_high=f.interval_high,
        confidence=f.confidence,
        model=f.model,
        model_version=f.model_version,
        scenario=f.scenario,
        status=f.status,
        data_version=f.data_version,
        valid_from=f.valid_from.isoformat() if f.valid_from else None,
    )


@router.post("/run", response_model=ForecastOutcomeRead)
def run_forecast(
    target: str = Query(...),
    method: str = Query(default="all"),
    horizon: str = Query(default="short"),
    scenario: str = Query(default="base"),
    db: Session = Depends(get_db),
) -> ForecastOutcomeRead:
    """اجرای baseline برای یک هدف و ثبت در Ledger (جانشینی خودکار)."""
    outcome = ForecastEngine(db).run(
        target=target, method=method, horizon=horizon, scenario=scenario
    )
    return ForecastOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[ForecastRead])
def list_forecasts(
    target: str | None = None,
    model: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ForecastRead]:
    stmt = select(Forecast).order_by(Forecast.created_at.desc()).limit(limit)
    if target:
        stmt = stmt.where(Forecast.target == target)
    if model:
        stmt = stmt.where(Forecast.model == model)
    return [_to_forecast(f) for f in db.execute(stmt).scalars().all()]


@router.get("/ledger/active", response_model=list[ForecastRead])
def ledger_active(
    as_of: datetime = Query(..., description="ISO-8601 timezone-aware"),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[ForecastRead]:
    """پیش‌بینی‌های فعال در زمان as_of."""
    from domains.forecast.ledger import active_as_of

    if as_of.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must be timezone-aware")
    return [_to_forecast(f) for f in active_as_of(db, as_of=as_of, limit=limit)]


@router.get("/{forecast_id}", response_model=ForecastRead)
def get_forecast(
    forecast_id: uuid.UUID, db: Session = Depends(get_db)
) -> ForecastRead:
    forecast = db.get(Forecast, forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    return _to_forecast(forecast)


@router.post("/{forecast_id}/supersede", response_model=ForecastRead)
def supersede_forecast(
    forecast_id: uuid.UUID, db: Session = Depends(get_db)
) -> ForecastRead:
    """ابطال دستی یک پیش‌بینی فعال (بدون حذف از Ledger)."""
    from domains.forecast.ledger import mark_superseded

    forecast = mark_superseded(db, forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    return _to_forecast(forecast)
