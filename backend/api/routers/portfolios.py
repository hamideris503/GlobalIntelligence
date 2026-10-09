"""Portfolio Intelligence API (Phase 35).

- POST   /api/portfolios                 → ساخت پورتفوی
- GET    /api/portfolios                 → لیست پورتفوی‌ها
- GET    /api/portfolios/{id}            → یک پورتفوی
- DELETE /api/portfolios/{id}            → حذف پورتفوی (+ snapshotها)
- POST   /api/portfolios/{id}/snapshot   → snapshot تحلیلی ماهانه
- GET    /api/portfolios/{id}/snapshots  → تاریخچه‌ی snapshotها
"""
from __future__ import annotations

import json
import uuid

from domains.portfolio.engine import PortfolioEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.portfolio import Portfolio, PortfolioSnapshot
from backend.database.session import get_db

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class PortfolioCreate(BaseModel):
    name: str
    positions: dict[str, float]
    notes: str | None = None


class PortfolioRead(BaseModel):
    id: str
    name: str
    positions: dict[str, float]
    notes: str | None


class SnapshotOutcomeRead(BaseModel):
    portfolio_id: str
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class SnapshotRead(BaseModel):
    id: str
    period: str
    expected_return: float | None
    uncertainty: float | None
    concentration: float | None
    diversification: float | None
    coverage: float | None
    detail: list[dict]
    method: str | None
    confidence: float | None


def _parse_positions(raw: str | None) -> dict[str, float]:
    try:
        out = json.loads(raw or "{}")
        return {str(k): float(v) for k, v in out.items()} if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _to_portfolio(p: Portfolio) -> PortfolioRead:
    return PortfolioRead(
        id=str(p.id), name=p.name, positions=_parse_positions(p.positions), notes=p.notes
    )


def _to_snapshot(s: PortfolioSnapshot) -> SnapshotRead:
    try:
        detail = json.loads(s.detail or "[]")
    except Exception:  # noqa: BLE001
        detail = []
    return SnapshotRead(
        id=str(s.id),
        period=s.period,
        expected_return=s.expected_return,
        uncertainty=s.uncertainty,
        concentration=s.concentration,
        diversification=s.diversification,
        coverage=s.coverage,
        detail=detail if isinstance(detail, list) else [],
        method=s.method,
        confidence=s.confidence,
    )


@router.post("", response_model=PortfolioRead)
def create_portfolio(req: PortfolioCreate, db: Session = Depends(get_db)) -> PortfolioRead:
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty")
    if not req.positions:
        raise HTTPException(status_code=422, detail="positions must not be empty")
    existing = db.execute(
        select(Portfolio).where(Portfolio.name == req.name.strip())
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="portfolio name already exists")
    portfolio = Portfolio(
        name=req.name.strip(),
        positions=json.dumps(req.positions, ensure_ascii=False),
        notes=req.notes,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return _to_portfolio(portfolio)


@router.get("", response_model=list[PortfolioRead])
def list_portfolios(db: Session = Depends(get_db)) -> list[PortfolioRead]:
    stmt = select(Portfolio).order_by(Portfolio.name)
    return [_to_portfolio(p) for p in db.execute(stmt).scalars().all()]


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> PortfolioRead:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return _to_portfolio(portfolio)


@router.delete("/{portfolio_id}", response_model=dict)
def delete_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    db.delete(portfolio)
    db.commit()
    return {"deleted": True}


@router.post("/{portfolio_id}/snapshot", response_model=SnapshotOutcomeRead)
def snapshot_portfolio(
    portfolio_id: uuid.UUID,
    period: str | None = None,
    db: Session = Depends(get_db),
) -> SnapshotOutcomeRead:
    outcome = PortfolioEngine(db).snapshot(
        portfolio_id=str(portfolio_id), period=period
    )
    if outcome.failed and not outcome.stored and not outcome.duplicates:
        raise HTTPException(status_code=404, detail="; ".join(outcome.errors) or "failed")
    return SnapshotOutcomeRead(**outcome.as_dict())


@router.get("/{portfolio_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    portfolio_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SnapshotRead]:
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioSnapshot.period.desc())
        .limit(limit)
    )
    return [_to_snapshot(s) for s in db.execute(stmt).scalars().all()]
