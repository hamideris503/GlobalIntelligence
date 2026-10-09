"""Geopolitical Engine API (Phase 22).

- POST /api/geopolitics/analyze  → تحلیل تنش بازیگران و ذخیره‌ی assessment
- GET  /api/geopolitics/assessments → لیست assessmentها (فیلتر بازیگر/دوره)
- GET  /api/geopolitics/tensions    → تنش‌های دوره‌ی جاری به ترتیب نزولی
"""
from __future__ import annotations

from domains.geopolitics.analysis import GeopoliticalEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.session import get_db

router = APIRouter(prefix="/api/geopolitics", tags=["geopolitics"])


class GeoOutcomeRead(BaseModel):
    actors_analyzed: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class GeoAssessmentRead(BaseModel):
    id: str
    actor: str
    period: str
    tension: float | None
    conflict_share: float | None
    event_count: int | None
    sanction_links: int | None
    top_types: dict
    method: str | None
    confidence: float | None
    observed_at: str | None


def _to_assessment(a: GeopoliticalAssessment) -> GeoAssessmentRead:
    import json

    try:
        top = json.loads(a.top_types or "{}")
    except Exception:  # noqa: BLE001
        top = {}
    return GeoAssessmentRead(
        id=str(a.id),
        actor=a.actor,
        period=a.period,
        tension=a.tension,
        conflict_share=a.conflict_share,
        event_count=a.event_count,
        sanction_links=a.sanction_links,
        top_types=top if isinstance(top, dict) else {},
        method=a.method,
        confidence=a.confidence,
        observed_at=a.observed_at.isoformat() if a.observed_at else None,
    )


@router.post("/analyze", response_model=GeoOutcomeRead)
def analyze_geopolitics(
    period: str | None = None, db: Session = Depends(get_db)
) -> GeoOutcomeRead:
    """تحلیل تنش بازیگران و ذخیره‌ی assessment (idempotent در ماه)."""
    outcome = GeopoliticalEngine(db).analyze_all(period=period)
    return GeoOutcomeRead(**outcome.as_dict())


@router.get("/assessments", response_model=list[GeoAssessmentRead])
def list_assessments(
    actor: str | None = None,
    period: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[GeoAssessmentRead]:
    stmt = (
        select(GeopoliticalAssessment)
        .order_by(
            GeopoliticalAssessment.tension.desc().nullslast(),
            GeopoliticalAssessment.actor,
        )
        .limit(limit)
    )
    if actor:
        stmt = stmt.where(GeopoliticalAssessment.actor == actor)
    if period:
        stmt = stmt.where(GeopoliticalAssessment.period == period)
    return [_to_assessment(a) for a in db.execute(stmt).scalars().all()]


@router.get("/tensions", response_model=list[GeoAssessmentRead])
def current_tensions(
    period: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[GeoAssessmentRead]:
    """تنش‌های یک دوره (پیش‌فرض: آخرین دوره‌ی موجود) به ترتیب نزولی."""
    if period is None:
        stmt = select(GeopoliticalAssessment.period).order_by(
            GeopoliticalAssessment.period.desc()
        ).limit(1)
        period = db.execute(stmt).scalars().first()
        if period is None:
            return []
    stmt = (
        select(GeopoliticalAssessment)
        .where(GeopoliticalAssessment.period == period)
        .order_by(GeopoliticalAssessment.tension.desc().nullslast())
        .limit(limit)
    )
    return [_to_assessment(a) for a in db.execute(stmt).scalars().all()]
