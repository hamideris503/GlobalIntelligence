"""Briefings API (Phase 41).

- POST /api/briefings/daily → ساخت خلاصه‌ی روزانه
- GET  /api/briefings         → لیست گزارش‌ها (فیلتر نوع/دوره)
- GET  /api/briefings/{id}    → یک گزارش با محتوا
"""
from __future__ import annotations

import json
import uuid

from domains.briefings.daily import DailyBriefingService
from domains.briefings.weekly import WeeklyBriefingService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.briefing import Briefing
from backend.database.session import get_db

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


class DailyOutcomeRead(BaseModel):
    briefing_id: str
    period: str
    stored: int
    duplicates: int
    sections: dict


class BriefingRead(BaseModel):
    id: str
    kind: str
    period: str
    title: str | None
    content: dict
    method: str | None
    observed_at: str | None


def _to_briefing(b: Briefing) -> BriefingRead:
    try:
        content = json.loads(b.content or "{}")
    except Exception:  # noqa: BLE001
        content = {}
    return BriefingRead(
        id=str(b.id),
        kind=b.kind,
        period=b.period,
        title=b.title,
        content=content if isinstance(content, dict) else {},
        method=b.method,
        observed_at=b.observed_at.isoformat() if b.observed_at else None,
    )


@router.post("/daily", response_model=DailyOutcomeRead)
def build_daily(
    day: str | None = None,
    window_hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> DailyOutcomeRead:
    """ساخت خلاصه‌ی روزانه (idempotent در روز)."""
    outcome = DailyBriefingService(db).build(day=day, window_hours=window_hours)
    return DailyOutcomeRead(**outcome.as_dict())


@router.post("/weekly", response_model=DailyOutcomeRead)
def build_weekly(db: Session = Depends(get_db)) -> DailyOutcomeRead:
    """ساخت خلاصه‌ی هفتگی (idempotent در هفته‌ی ISO)."""
    outcome = WeeklyBriefingService(db).build()
    return DailyOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[BriefingRead])
def list_briefings(
    kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[BriefingRead]:
    stmt = (
        select(Briefing).order_by(Briefing.period.desc()).limit(limit)
    )
    if kind:
        stmt = stmt.where(Briefing.kind == kind)
    return [_to_briefing(b) for b in db.execute(stmt).scalars().all()]


@router.get("/{briefing_id}", response_model=BriefingRead)
def get_briefing(
    briefing_id: uuid.UUID, db: Session = Depends(get_db)
) -> BriefingRead:
    briefing = db.get(Briefing, briefing_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="briefing not found")
    return _to_briefing(briefing)
