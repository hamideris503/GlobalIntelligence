"""Historical Analogue API (Phase 20).

- GET /api/analogues?snapshot_id=&top_k=&metric= → وضعیت‌های تاریخی مشابه
- GET /api/analogues/{id}/aftermath?limit= → «بعدش چه شد»
"""
from __future__ import annotations

from domains.analogue.engine import AnalogueService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/analogues", tags=["analogues"])


class AnalogueHitRead(BaseModel):
    snapshot_id: str
    captured_at: str
    distance: float
    similarity: float
    macro_regime: str | None
    market_regime: str | None
    deltas: dict[str, float]
    compared_dims: int
    coverage: float


class AnalogueOutcomeRead(BaseModel):
    reference_id: str
    metric: str
    valid_dims: int
    min_valid_dims: int
    hits: list[AnalogueHitRead]


class AftermathOutcomeRead(BaseModel):
    analogue_id: str
    next_snapshots: list[dict]
    next_events: list[dict]


@router.get("", response_model=AnalogueOutcomeRead)
def find_analogues(
    snapshot_id: str | None = None,
    top_k: int = Query(default=5, ge=1, le=50),
    metric: str = Query(default="euclidean"),
    db: Session = Depends(get_db),
) -> AnalogueOutcomeRead:
    """وضعیت‌های تاریخی مشابه وضعیت مرجع (پیش‌فرض: آخرین snapshot)."""
    try:
        outcome = AnalogueService(db).find_analogues(
            snapshot_id=snapshot_id, top_k=top_k, metric=metric
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AnalogueOutcomeRead(**outcome.as_dict())


@router.get("/{analogue_id}/aftermath", response_model=AftermathOutcomeRead)
def aftermath(
    analogue_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
) -> AftermathOutcomeRead:
    """«بعد از این وضعیت تاریخی چه شد» — snapshotها و رویدادهای بعدی."""
    try:
        outcome = AnalogueService(db).aftermath(analogue_id=analogue_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AftermathOutcomeRead(**outcome.as_dict())
