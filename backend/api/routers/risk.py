"""Risk Engine API (Phase 31).

- POST /api/risk/analyze  → تحلیل ریسک‌ها و ذخیره‌ی assessment
- GET  /api/risk/assessments → لیست assessmentها (فیلتر دسته/دوره)
- GET  /api/risk/overview    → آخرین وضعیت هر دسته
"""
from __future__ import annotations

import json

from domains.risk.analysis import RiskEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.risk_assessment import RiskAssessment
from backend.database.session import get_db

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskOutcomeRead(BaseModel):
    categories_analyzed: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class RiskAssessmentRead(BaseModel):
    id: str
    category: str
    period: str
    score: float | None
    level: str | None
    probability: float | None = None
    impact: float | None = None
    evidence_count: int | None = None
    drivers: list[str]
    method: str | None
    confidence: float | None
    observed_at: str | None


def _to_assessment(a: RiskAssessment, evidence_count: int | None = None) -> RiskAssessmentRead:
    try:
        drivers = json.loads(a.drivers or "[]")
    except Exception:  # noqa: BLE001
        drivers = []
    return RiskAssessmentRead(
        id=str(a.id),
        category=a.category,
        period=a.period,
        score=a.score,
        level=a.level,
        probability=a.probability,
        impact=a.impact,
        evidence_count=evidence_count,
        drivers=drivers if isinstance(drivers, list) else [],
        method=a.method,
        confidence=a.confidence,
        observed_at=a.observed_at.isoformat() if a.observed_at else None,
    )


@router.post("/analyze", response_model=RiskOutcomeRead)
def analyze_risks(
    period: str | None = None, db: Session = Depends(get_db)
) -> RiskOutcomeRead:
    """تحلیل ریسک‌ها و ذخیره‌ی assessment (idempotent در ماه)."""
    outcome = RiskEngine(db).analyze_all(period=period)
    return RiskOutcomeRead(**outcome.as_dict())


@router.get("/assessments", response_model=list[RiskAssessmentRead])
def list_assessments(
    category: str | None = None,
    period: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[RiskAssessmentRead]:
    stmt = (
        select(RiskAssessment)
        .order_by(RiskAssessment.category, RiskAssessment.period.desc())
        .limit(limit)
    )
    if category:
        stmt = stmt.where(RiskAssessment.category == category)
    if period:
        stmt = stmt.where(RiskAssessment.period == period)
    return [_to_assessment(a) for a in db.execute(stmt).scalars().all()]


@router.get("/overview", response_model=list[RiskAssessmentRead])
def overview(db: Session = Depends(get_db)) -> list[RiskAssessmentRead]:
    """آخرین وضعیت هر دسته (پرخطرترین اول)."""
    stmt = select(RiskAssessment).order_by(
        RiskAssessment.category, RiskAssessment.period.desc()
    )
    seen: set[str] = set()
    out: list[RiskAssessmentRead] = []
    for a in db.execute(stmt).scalars().all():
        if a.category in seen:
            continue
        seen.add(a.category)
        out.append(_to_assessment(a))
    out.sort(key=lambda r: (r.score is None, -(r.score or 0.0)))
    return out


@router.get("/matrix")
def risk_matrix(
    period: str | None = None, db: Session = Depends(get_db)
) -> dict:
    """ماتریس ۵×۵ احتمال × شدت.

    فقط ردیف‌هایی که هم `probability` و هم `impact` دارند شمرده می‌شوند؛ بقیه
    در `without_probability_impact` می‌آیند. بدون این دو مقدار هیچ سلولی جعل
    نمی‌شود.
    """
    stmt = select(RiskAssessment).order_by(RiskAssessment.category)
    if period:
        stmt = stmt.where(RiskAssessment.period == period)
    rows = db.execute(stmt).scalars().all()

    cells = [[0] * 5 for _ in range(5)]  # cells[impact-1][probability-1]
    without: list[str] = []
    with_pi: list[dict] = []
    for r in rows:
        if r.probability is None or r.impact is None:
            without.append(r.category)
            continue
        pi = min(4, max(0, int(r.probability * 5)))
        im = min(4, max(0, int(r.impact * 5)))
        cells[im][pi] += 1
        with_pi.append({
            "category": r.category,
            "probability": r.probability,
            "impact": r.impact,
            "score": r.score,
        })
    return {
        "period": period,
        "cells": cells,
        "items": with_pi,
        "without_probability_impact": without,
        "with_probability_impact": len(with_pi),
        "total": len(rows),
    }
