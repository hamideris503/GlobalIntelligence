"""Economic Data API (Phase 16).

- POST /api/economic/fetch     → دریافت داده از World Bank
- GET  /api/economic/observations → لیست مشاهدات (فیلتر شاخص/کشور)
- GET  /api/economic/indicators   → لیست شاخص‌های موجود
- GET  /api/economic/latest       → آخرین مقدار هر شاخص/کشور
"""
from __future__ import annotations

import json

from domains.macro.engine import EconomicDataService
from domains.macro.fetchers import WB_INDICATORS
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.market import MacroObservation
from backend.database.session import get_db

router = APIRouter(prefix="/api/economic", tags=["economic"])


class EconomicOutcomeRead(BaseModel):
    fetched: int
    stored: int
    duplicates: int
    failed: int
    errors: list[str]


class ObservationRead(BaseModel):
    id: str
    indicator: str
    country: str | None
    period: str | None
    value: float | None
    unit: str | None
    frequency: str | None
    source_name: str | None
    series_id: str | None


def _parse_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _to_obs(o: MacroObservation) -> ObservationRead:
    return ObservationRead(
        id=str(o.id),
        indicator=o.indicator,
        country=o.country,
        period=o.period,
        value=o.value,
        unit=o.unit,
        frequency=o.frequency,
        source_name=o.source_name,
        series_id=o.series_id,
    )


@router.post("/fetch", response_model=EconomicOutcomeRead)
async def fetch_economic(
    indicator: str | None = Query(default=None),
    country: str = Query(default="USA"),
    limit: int = Query(default=10, ge=1, le=100),
    fetcher: str = Query(default="world_bank"),
    db: Session = Depends(get_db),
) -> EconomicOutcomeRead:
    """دریافت داده‌ی اقتصادی از World Bank."""
    service = EconomicDataService(db, fetcher_name=fetcher)
    if indicator:
        outcome = await service.fetch_indicator(
            indicator=indicator, country=country, limit=limit
        )
    else:
        outcome = await service.run(limit=limit)
    return EconomicOutcomeRead(**outcome.as_dict())


@router.get("/observations", response_model=list[ObservationRead])
def list_observations(
    indicator: str | None = None,
    country: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ObservationRead]:
    stmt = select(MacroObservation).order_by(
        MacroObservation.indicator, MacroObservation.country, MacroObservation.period
    ).limit(limit)
    if indicator:
        stmt = stmt.where(MacroObservation.indicator == indicator)
    if country:
        stmt = stmt.where(MacroObservation.country == country)
    return [_to_obs(o) for o in db.execute(stmt).scalars().all()]


@router.get("/indicators")
def list_indicators() -> dict:
    """لیست شاخص‌های پشتیبانی‌شده با کد بانک جهانی."""
    return {
        key: {"code": val["code"], "unit": val["unit"], "frequency": val["frequency"]}
        for key, val in WB_INDICATORS.items()
    }


@router.get("/latest", response_model=list[ObservationRead])
def latest_observations(
    indicator: str | None = None,
    country: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ObservationRead]:
    """آخرین مشاهده‌ی هر (شاخص، کشور) بر اساس period."""
    stmt = select(MacroObservation).order_by(MacroObservation.period.desc()).limit(limit)
    if indicator:
        stmt = stmt.where(MacroObservation.indicator == indicator)
    if country:
        stmt = stmt.where(MacroObservation.country == country)
    return [_to_obs(o) for o in db.execute(stmt).scalars().all()]
