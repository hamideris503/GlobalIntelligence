"""Narrative Engine API (Phase 24).

- POST /api/narratives/build → ساخت روایت‌ها از رویدادها
- GET  /api/narratives          → لیست روایت‌ها (فیلتر دوره)
- GET  /api/narratives/{id}     → یک روایت
"""
from __future__ import annotations

import json
import uuid

from domains.narratives.engine import NarrativeEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.narrative import Narrative
from backend.database.session import get_db

router = APIRouter(prefix="/api/narratives", tags=["narratives"])


class NarrativeOutcomeRead(BaseModel):
    narratives_built: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class NarrativeRead(BaseModel):
    id: str
    title: str
    summary: str | None
    period: str
    signature: str
    event_ids: list[str]
    event_count: int | None
    article_count: int | None
    source_count: int | None
    first_seen: str | None
    last_seen: str | None
    dominant_stance: str | None
    stance_divergence: float | None
    strength: float | None
    method: str | None
    confidence: float | None
    observed_at: str | None


def _to_narrative(n: Narrative) -> NarrativeRead:
    try:
        ids = json.loads(n.event_ids or "[]")
    except Exception:  # noqa: BLE001
        ids = []
    return NarrativeRead(
        id=str(n.id),
        title=n.title,
        summary=n.summary,
        period=n.period,
        signature=n.signature,
        event_ids=ids if isinstance(ids, list) else [],
        event_count=n.event_count,
        article_count=n.article_count,
        source_count=n.source_count,
        first_seen=n.first_seen.isoformat() if n.first_seen else None,
        last_seen=n.last_seen.isoformat() if n.last_seen else None,
        dominant_stance=n.dominant_stance,
        stance_divergence=n.stance_divergence,
        strength=n.strength,
        method=n.method,
        confidence=n.confidence,
        observed_at=n.observed_at.isoformat() if n.observed_at else None,
    )


@router.post("/build", response_model=NarrativeOutcomeRead)
def build_narratives(
    period: str | None = None, db: Session = Depends(get_db)
) -> NarrativeOutcomeRead:
    """ساخت روایت‌ها از رویدادها (idempotent در ماه)."""
    outcome = NarrativeEngine(db).build_all(period=period)
    return NarrativeOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[NarrativeRead])
def list_narratives(
    period: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[NarrativeRead]:
    stmt = (
        select(Narrative)
        .order_by(Narrative.strength.desc().nullslast())
        .limit(limit)
    )
    if period:
        stmt = stmt.where(Narrative.period == period)
    return [_to_narrative(n) for n in db.execute(stmt).scalars().all()]


@router.get("/{narrative_id}", response_model=NarrativeRead)
def get_narrative(narrative_id: uuid.UUID, db: Session = Depends(get_db)) -> NarrativeRead:
    narrative = db.get(Narrative, narrative_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail="narrative not found")
    return _to_narrative(narrative)
