"""Social Intelligence API (Phase 23).

- POST /api/society/analyze  → تحلیل فضای اجتماعی و ذخیره‌ی assessment
- GET  /api/society/assessments → لیست assessmentها (فیلتر قلمرو/دوره)
- GET  /api/society/mood        → آخرین وضعیت هر قلمرو
"""
from __future__ import annotations

import json

from domains.society.analysis import SocialEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.social_assessment import SocialAssessment
from backend.database.session import get_db

router = APIRouter(prefix="/api/society", tags=["society"])


class SocialOutcomeRead(BaseModel):
    scopes_analyzed: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class SocialAssessmentRead(BaseModel):
    id: str
    scope_type: str
    scope: str
    period: str
    avg_sentiment: float | None
    article_count: int | None
    unrest_share: float | None
    stance_mix: dict
    method: str | None
    confidence: float | None
    observed_at: str | None


def _to_assessment(a: SocialAssessment) -> SocialAssessmentRead:
    try:
        mix = json.loads(a.stance_mix or "{}")
    except Exception:  # noqa: BLE001
        mix = {}
    return SocialAssessmentRead(
        id=str(a.id),
        scope_type=a.scope_type,
        scope=a.scope,
        period=a.period,
        avg_sentiment=a.avg_sentiment,
        article_count=a.article_count,
        unrest_share=a.unrest_share,
        stance_mix=mix if isinstance(mix, dict) else {},
        method=a.method,
        confidence=a.confidence,
        observed_at=a.observed_at.isoformat() if a.observed_at else None,
    )


@router.post("/analyze", response_model=SocialOutcomeRead)
def analyze_society(
    period: str | None = None, db: Session = Depends(get_db)
) -> SocialOutcomeRead:
    """تحلیل فضای اجتماعی و ذخیره‌ی assessment (idempotent در ماه)."""
    outcome = SocialEngine(db).analyze_all(period=period)
    return SocialOutcomeRead(**outcome.as_dict())


@router.get("/assessments", response_model=list[SocialAssessmentRead])
def list_assessments(
    scope_type: str | None = None,
    scope: str | None = None,
    period: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[SocialAssessmentRead]:
    stmt = (
        select(SocialAssessment)
        .order_by(SocialAssessment.scope_type, SocialAssessment.scope)
        .limit(limit)
    )
    if scope_type:
        stmt = stmt.where(SocialAssessment.scope_type == scope_type)
    if scope:
        stmt = stmt.where(SocialAssessment.scope == scope)
    if period:
        stmt = stmt.where(SocialAssessment.period == period)
    return [_to_assessment(a) for a in db.execute(stmt).scalars().all()]


@router.get("/mood", response_model=list[SocialAssessmentRead])
def current_mood(
    scope_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[SocialAssessmentRead]:
    """آخرین وضعیت هر قلمرو (جدیدترین دوره)."""
    stmt = select(SocialAssessment).order_by(
        SocialAssessment.scope_type,
        SocialAssessment.scope,
        SocialAssessment.period.desc(),
    )
    if scope_type:
        stmt = stmt.where(SocialAssessment.scope_type == scope_type)
    seen: set[tuple[str, str]] = set()
    out: list[SocialAssessmentRead] = []
    for a in db.execute(stmt).scalars().all():
        key = (a.scope_type, a.scope)
        if key in seen:
            continue
        seen.add(key)
        out.append(_to_assessment(a))
    return out
