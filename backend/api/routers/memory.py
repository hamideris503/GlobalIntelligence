"""Historical Memory API (Phase 19).

- POST /api/memory/archive   → بایگانی رویدادها/حالت‌ها/داده‌های خام مهم
- GET  /api/memory/timeline  → «در زمان T چه می‌دانستیم؟» (Point-in-Time)
- GET  /api/memory/stats     → شمارش هر لایه
- GET  /api/memory/records   → لیست رکوردها (فیلتر لایه)
"""
from __future__ import annotations

import json
from datetime import datetime

from domains.memory.service import HistoricalMemoryService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.memory import MemoryRecord
from backend.database.session import get_db

router = APIRouter(prefix="/api/memory", tags=["memory"])


class ArchiveOutcomeRead(BaseModel):
    raw_archived: int
    events_archived: int
    states_archived: int
    duplicates: int
    failed: int
    errors: list[str]


class RecordRead(BaseModel):
    id: str
    layer: str
    ref_type: str
    ref_id: str
    title: str | None
    summary: str | None
    importance: float | None
    observed_at: str | None
    recorded_at: str | None
    record_metadata: dict


def _to_record(r: MemoryRecord) -> RecordRead:
    try:
        meta = json.loads(r.record_metadata or "{}")
    except Exception:  # noqa: BLE001
        meta = {}
    return RecordRead(
        id=str(r.id),
        layer=r.layer,
        ref_type=r.ref_type,
        ref_id=r.ref_id,
        title=r.title,
        summary=r.summary,
        importance=r.importance,
        observed_at=r.observed_at.isoformat() if r.observed_at else None,
        recorded_at=r.recorded_at.isoformat() if r.recorded_at else None,
        record_metadata=meta if isinstance(meta, dict) else {},
    )


@router.post("/archive", response_model=ArchiveOutcomeRead)
def archive_memory(
    limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db)
) -> ArchiveOutcomeRead:
    """بایگانی موارد مهم هر سه لایه‌ی raw/event/state."""
    outcome = HistoricalMemoryService(db).archive_all(limit=limit)
    return ArchiveOutcomeRead(**outcome.as_dict())


@router.get("/timeline", response_model=list[RecordRead])
def timeline(
    as_of: datetime = Query(..., description="ISO-8601, e.g. 2026-10-08T00:00:00Z"),
    layer: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[RecordRead]:
    """رکوردهای دانسته‌شده تا زمان as_of."""
    if as_of.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must be timezone-aware")
    return [
        _to_record(r)
        for r in HistoricalMemoryService(db).timeline(
            as_of=as_of, layer=layer, limit=limit
        )
    ]


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return HistoricalMemoryService(db).stats()


@router.get("/records", response_model=list[RecordRead])
def records(
    layer: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[RecordRead]:
    stmt = select(MemoryRecord).order_by(MemoryRecord.observed_at.desc()).limit(limit)
    if layer:
        stmt = stmt.where(MemoryRecord.layer == layer)
    return [_to_record(r) for r in db.execute(stmt).scalars().all()]
