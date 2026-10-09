"""Iran Mode API (Phase 33).

- GET /api/iran/brief  → بسته‌ی اطلاعاتی ایران (رویداد/ادعا/macro/تصمیم/بستر)
- GET /api/iran/events → رویدادهای مرتبط با ایران
"""
from __future__ import annotations

import json

from domains.iran.brief import IranModeService
from domains.iran.transmission import TransmissionEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.transmission_assessment import TransmissionAssessment
from backend.database.session import get_db

router = APIRouter(prefix="/api/iran", tags=["iran"])


class IranBriefRead(BaseModel):
    events: list[dict]
    claims: list[dict]
    macro: list[dict]
    decisions: list[dict]
    world_state: dict
    counts: dict[str, int]


class IranEventRead(BaseModel):
    id: str
    event_type: str | None
    action: str | None
    occurred_at: str | None


class TransmissionOutcomeRead(BaseModel):
    channels_analyzed: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class TransmissionRead(BaseModel):
    channel: str
    period: str
    input_value: float | None
    exposure: float | None
    impact: float | None
    drivers: list[str]
    method: str | None
    confidence: float | None


@router.get("/brief", response_model=IranBriefRead)
def iran_brief(
    limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)
) -> IranBriefRead:
    """بسته‌ی اطلاعاتی ایران از خروجی‌های موجود."""
    return IranBriefRead(**IranModeService(db).brief(limit=limit).as_dict())


@router.get("/events", response_model=list[IranEventRead])
def iran_events(
    limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)
) -> list[IranEventRead]:
    return [
        IranEventRead(
            id=str(e.id),
            event_type=e.event_type,
            action=(e.action or "")[:300],
            occurred_at=e.occurred_at.isoformat() if e.occurred_at else None,
        )
        for e in IranModeService(db).iran_events(limit=limit)
    ]


@router.post("/transmission/analyze", response_model=TransmissionOutcomeRead)
def analyze_transmission(
    period: str | None = None, db: Session = Depends(get_db)
) -> TransmissionOutcomeRead:
    """تحلیل کانال‌های انتقال شوک جهانی به ایران (idempotent در ماه)."""
    outcome = TransmissionEngine(db).analyze_all(period=period)
    return TransmissionOutcomeRead(**outcome.as_dict())


@router.get("/transmission", response_model=list[TransmissionRead])
def list_transmission(
    period: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TransmissionRead]:
    stmt = (
        select(TransmissionAssessment)
        .order_by(TransmissionAssessment.impact.desc().nullslast())
        .limit(limit)
    )
    if period:
        stmt = stmt.where(TransmissionAssessment.period == period)
    out = []
    for t in db.execute(stmt).scalars().all():
        try:
            drivers = json.loads(t.drivers or "[]")
        except Exception:  # noqa: BLE001
            drivers = []
        out.append(
            TransmissionRead(
                channel=t.channel,
                period=t.period,
                input_value=t.input_value,
                exposure=t.exposure,
                impact=t.impact,
                drivers=drivers if isinstance(drivers, list) else [],
                method=t.method,
                confidence=t.confidence,
            )
        )
    return out
