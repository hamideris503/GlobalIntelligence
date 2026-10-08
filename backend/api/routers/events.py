"""Event Extraction API (Phase 11)."""
from __future__ import annotations

import json

from domains.events.extractor import EventExtractor
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.event import Event
from backend.database.session import get_db

router = APIRouter(prefix="/api/events", tags=["events"])


class EventOutcomeRead(BaseModel):
    events_created: int
    articles_linked: int
    failed: int
    errors: list[str]


class EventRead(BaseModel):
    id: str
    event_type: str | None
    action: str | None
    location: str | None
    actors: list[str]
    affected_assets: list[str]
    confidence: float | None
    occurred_at: str | None
    article_count: int


@router.post("/extract", response_model=EventOutcomeRead)
async def extract_events(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> EventOutcomeRead:
    """استخراج رویداد از خوشه‌های مقالات طبقه‌بندی‌شده."""
    outcome = await EventExtractor(db).run(limit=limit)
    return EventOutcomeRead(
        events_created=outcome.events_created,
        articles_linked=outcome.articles_linked,
        failed=outcome.failed,
        errors=outcome.errors,
    )


@router.get("", response_model=list[EventRead])
def list_events(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> list[EventRead]:
    rows = (
        db.execute(select(Event).order_by(Event.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        EventRead(
            id=str(e.id),
            event_type=e.event_type,
            action=e.action,
            location=e.location,
            actors=_parse_list(e.actors),
            affected_assets=_parse_list(e.affected_assets),
            confidence=e.confidence,
            occurred_at=e.occurred_at.isoformat() if e.occurred_at else None,
            article_count=len(e.articles),
        )
        for e in rows
    ]


def _parse_list(value: str | None) -> list:
    if not value:
        return []
    try:
        out = json.loads(value)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []
