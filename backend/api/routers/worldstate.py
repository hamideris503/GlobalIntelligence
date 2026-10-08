"""World State API (Phase 18).

- POST /api/world-state/build → ساخت snapshot جدید وضعیت جهان
- GET  /api/world-state/current → آخرین snapshot
- GET  /api/world-state/history → تاریخچه‌ی snapshotها
"""
from __future__ import annotations

import json

from domains.worldstate.builder import WorldStateBuilder
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.world_state import WorldState
from backend.database.session import get_db

router = APIRouter(prefix="/api/world-state", tags=["world-state"])


class SnapshotRead(BaseModel):
    id: str
    captured_at: str
    granularity: str | None
    growth_pressure: float | None
    inflation_pressure: float | None
    liquidity: float | None
    financial_stress: float | None
    geopolitical_risk: float | None
    energy_risk: float | None
    trade_risk: float | None
    political_risk: float | None
    social_pressure: float | None
    macro_regime: str | None
    market_regime: str | None
    confidence: float | None
    value_metadata: dict


class BuildOutcomeRead(BaseModel):
    snapshot_id: str
    captured_at: str
    macro_regime: str
    market_regime: str
    confidence: float
    signals: dict


def _to_snapshot(s: WorldState) -> SnapshotRead:
    try:
        meta = json.loads(s.value_metadata or "{}")
    except Exception:  # noqa: BLE001
        meta = {}
    return SnapshotRead(
        id=str(s.id),
        captured_at=s.captured_at.isoformat() if s.captured_at else "",
        granularity=s.granularity,
        growth_pressure=s.growth_pressure,
        inflation_pressure=s.inflation_pressure,
        liquidity=s.liquidity,
        financial_stress=s.financial_stress,
        geopolitical_risk=s.geopolitical_risk,
        energy_risk=s.energy_risk,
        trade_risk=s.trade_risk,
        political_risk=s.political_risk,
        social_pressure=s.social_pressure,
        macro_regime=s.macro_regime,
        market_regime=s.market_regime,
        confidence=s.confidence,
        value_metadata=meta if isinstance(meta, dict) else {},
    )


@router.post("/build", response_model=BuildOutcomeRead)
def build_snapshot(
    granularity: str = Query(default="daily"), db: Session = Depends(get_db)
) -> BuildOutcomeRead:
    """ساخت snapshot جدید وضعیت جهان از داده‌های macro/market/event."""
    outcome = WorldStateBuilder(db).build(granularity=granularity)
    return BuildOutcomeRead(**outcome.as_dict())


@router.get("/current", response_model=SnapshotRead)
def current_snapshot(db: Session = Depends(get_db)) -> SnapshotRead:
    """آخرین snapshot وضعیت جهان."""
    stmt = select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
    snapshot = db.execute(stmt).scalars().first()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no world state snapshot yet")
    return _to_snapshot(snapshot)


@router.get("/history", response_model=list[SnapshotRead])
def history(
    limit: int = Query(default=30, ge=1, le=500), db: Session = Depends(get_db)
) -> list[SnapshotRead]:
    stmt = (
        select(WorldState).order_by(WorldState.captured_at.desc()).limit(limit)
    )
    return [_to_snapshot(s) for s in db.execute(stmt).scalars().all()]
