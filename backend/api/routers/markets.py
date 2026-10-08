"""Market Data API (Phase 17).

- POST /api/markets/fetch       → دریافت نقل‌قول (یک نماد / کلاس دارایی / همه)
- GET  /api/markets/observations → لیست مشاهدات (فیلتر نماد/کلاس)
- GET  /api/markets/symbols       → کاتالوگ نمادها
- GET  /api/markets/latest        → آخرین مشاهده‌ی هر نماد
"""
from __future__ import annotations

from domains.markets.engine import MarketDataService
from domains.markets.fetchers import SYMBOLS
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.market import MarketObservation
from backend.database.session import get_db

router = APIRouter(prefix="/api/markets", tags=["markets"])


class MarketOutcomeRead(BaseModel):
    fetched: int
    stored: int
    duplicates: int
    failed: int
    errors: list[str]


class QuoteRead(BaseModel):
    id: str
    symbol: str
    asset_class: str | None
    value: float | None
    unit: str | None
    currency: str | None
    source_name: str | None
    observed_at: str | None


def _to_quote(o: MarketObservation) -> QuoteRead:
    return QuoteRead(
        id=str(o.id),
        symbol=o.symbol,
        asset_class=o.asset_class,
        value=o.value,
        unit=o.unit,
        currency=o.currency,
        source_name=o.source_name,
        observed_at=o.observed_at.isoformat() if o.observed_at else None,
    )


@router.post("/fetch", response_model=MarketOutcomeRead)
async def fetch_markets(
    symbol: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    fetcher: str = Query(default="auto"),
    db: Session = Depends(get_db),
) -> MarketOutcomeRead:
    """دریافت داده‌ی بازار برای یک نماد، یک کلاس دارایی یا همه."""
    service = MarketDataService(db, fetcher_name=fetcher)
    if symbol:
        outcome = await service.fetch_symbol(symbol=symbol)
    else:
        outcome = await service.run(asset_class=asset_class)
    return MarketOutcomeRead(**outcome.as_dict())


@router.get("/observations", response_model=list[QuoteRead])
def list_observations(
    symbol: str | None = None,
    asset_class: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[QuoteRead]:
    stmt = (
        select(MarketObservation)
        .order_by(MarketObservation.symbol, MarketObservation.observed_at.desc())
        .limit(limit)
    )
    if symbol:
        stmt = stmt.where(MarketObservation.symbol == symbol)
    if asset_class:
        stmt = stmt.where(MarketObservation.asset_class == asset_class)
    return [_to_quote(o) for o in db.execute(stmt).scalars().all()]


@router.get("/symbols")
def list_symbols() -> dict:
    """کاتالوگ نمادهای پشتیبانی‌شده."""
    return dict(SYMBOLS)


@router.get("/latest", response_model=list[QuoteRead])
def latest_quotes(
    asset_class: str | None = None,
    db: Session = Depends(get_db),
) -> list[QuoteRead]:
    """آخرین مشاهده‌ی هر نماد (بر اساس observed_at)."""
    stmt = select(MarketObservation).order_by(
        MarketObservation.symbol, MarketObservation.observed_at.desc()
    )
    if asset_class:
        stmt = stmt.where(MarketObservation.asset_class == asset_class)
    seen: set[str] = set()
    out: list[QuoteRead] = []
    for o in db.execute(stmt).scalars().all():
        if o.symbol in seen:
            continue
        seen.add(o.symbol)
        out.append(_to_quote(o))
    return out
