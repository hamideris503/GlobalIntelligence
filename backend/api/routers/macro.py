"""Macro Engine API (Phase 21).

- POST /api/macro/analyze       → تحلیل سری‌ها و ذخیره‌ی assessment
- GET  /api/macro/assessments   → لیست assessmentها (فیلتر شاخص/کشور)
- GET  /api/macro/overview      → آخرین assessment هر شاخص برای یک کشور
"""
from __future__ import annotations

from domains.macro.analysis import MacroEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.macro_assessment import MacroAssessment
from backend.database.session import get_db

router = APIRouter(prefix="/api/macro", tags=["macro"])


class MacroOutcomeRead(BaseModel):
    series_analyzed: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class AssessmentRead(BaseModel):
    id: str
    indicator: str
    country: str | None
    period: str | None
    latest_value: float | None
    yoy_change: float | None
    acceleration: float | None
    z_score: float | None
    momentum: float | None
    momentum_label: str | None
    method: str | None
    confidence: float | None
    observed_at: str | None


def _to_assessment(a: MacroAssessment) -> AssessmentRead:
    return AssessmentRead(
        id=str(a.id),
        indicator=a.indicator,
        country=a.country,
        period=a.period,
        latest_value=a.latest_value,
        yoy_change=a.yoy_change,
        acceleration=a.acceleration,
        z_score=a.z_score,
        momentum=a.momentum,
        momentum_label=a.momentum_label,
        method=a.method,
        confidence=a.confidence,
        observed_at=a.observed_at.isoformat() if a.observed_at else None,
    )


@router.post("/analyze", response_model=MacroOutcomeRead)
def analyze_macro(
    indicator: str | None = None,
    country: str | None = None,
    db: Session = Depends(get_db),
) -> MacroOutcomeRead:
    """تحلیل سری‌های macro و ذخیره‌ی assessment (idempotent)."""
    outcome = MacroEngine(db).analyze_all(indicator=indicator, country=country)
    return MacroOutcomeRead(**outcome.as_dict())


@router.get("/assessments", response_model=list[AssessmentRead])
def list_assessments(
    indicator: str | None = None,
    country: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AssessmentRead]:
    stmt = (
        select(MacroAssessment)
        .order_by(MacroAssessment.indicator, MacroAssessment.country)
        .limit(limit)
    )
    if indicator:
        stmt = stmt.where(MacroAssessment.indicator == indicator)
    if country:
        stmt = stmt.where(MacroAssessment.country == country)
    return [_to_assessment(a) for a in db.execute(stmt).scalars().all()]


@router.get("/overview", response_model=list[AssessmentRead])
def overview(
    country: str = Query(...),
    db: Session = Depends(get_db),
) -> list[AssessmentRead]:
    """آخرین assessment هر شاخص برای یک کشور."""
    stmt = (
        select(MacroAssessment)
        .where(MacroAssessment.country == country)
        .order_by(MacroAssessment.indicator, MacroAssessment.period.desc())
    )
    seen: set[str] = set()
    out: list[AssessmentRead] = []
    for a in db.execute(stmt).scalars().all():
        if a.indicator in seen:
            continue
        seen.add(a.indicator)
        out.append(_to_assessment(a))
    return out
