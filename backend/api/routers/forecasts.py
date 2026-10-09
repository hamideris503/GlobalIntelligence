"""Forecast Engine API (Phase 25).

- POST /api/forecasts/run  → اجرای baseline و ثبت در Ledger (افزودنی)
- GET  /api/forecasts       → لیست پیش‌بینی‌ها (فیلتر هدف/مدل)
- GET  /api/forecasts/{id}  → یک پیش‌بینی
"""
from __future__ import annotations

import uuid

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
        data_version=f.data_version,
        valid_from=f.valid_from.isoformat() if f.valid_from else None,
    )


@router.post("/run", response_model=ForecastOutcomeRead)
def run_forecast(
    target: str = Query(...),
    method: str = Query(default="all"),
    horizon: str = Query(default="short"),
    db: Session = Depends(get_db),
) -> ForecastOutcomeRead:
    """اجرای baseline برای یک هدف و ثبت در Ledger."""
    outcome = ForecastEngine(db).run(target=target, method=method, horizon=horizon)
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


@router.get("/{forecast_id}", response_model=ForecastRead)
def get_forecast(
    forecast_id: uuid.UUID, db: Session = Depends(get_db)
) -> ForecastRead:
    forecast = db.get(Forecast, forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    return _to_forecast(forecast)
