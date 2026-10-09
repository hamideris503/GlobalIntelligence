"""Iran Mode API (Phase 33).

- GET /api/iran/brief  → بسته‌ی اطلاعاتی ایران (رویداد/ادعا/macro/تصمیم/بستر)
- GET /api/iran/events → رویدادهای مرتبط با ایران
"""
from __future__ import annotations

from domains.iran.brief import IranModeService
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
