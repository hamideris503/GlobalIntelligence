"""Long-Term Learning API (Phase 51).

- POST /api/learning/run → استخراج بینش از تاریخچه
- GET  /api/learning/insights → لیست بینش‌ها (فیلتر نوع)
"""
from __future__ import annotations

import json

from domains.learning.engine import LearningEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.learning_insight import LearningInsight
from backend.database.session import get_db

router = APIRouter(prefix="/api/learning", tags=["learning"])


class LearningOutcomeRead(BaseModel):
    insights_built: int
    stored: int
    duplicates: int
    skipped: int
    failed: int
    errors: list[str]


class InsightRead(BaseModel):
    kind: str
    subject: str
    period: str
    value: dict
    confidence: float | None
    method: str | None


def _to_insight(i: LearningInsight) -> InsightRead:
    try:
        value = json.loads(i.value or "{}")
    except Exception:  # noqa: BLE001
        value = {}
    return InsightRead(
        kind=i.kind,
        subject=i.subject,
        period=i.period,
        value=value if isinstance(value, dict) else {},
        confidence=i.confidence,
        method=i.method,
    )


@router.post("/run", response_model=LearningOutcomeRead)
def run_learning(
    period: str | None = None, db: Session = Depends(get_db)
) -> LearningOutcomeRead:
    """استخراج بینش از تاریخچه (idempotent در ماه)."""
    outcome = LearningEngine(db).run(period=period)
    return LearningOutcomeRead(**outcome.as_dict())


@router.get("/insights", response_model=list[InsightRead])
def list_insights(
    kind: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[InsightRead]:
    stmt = (
        select(LearningInsight)
        .order_by(LearningInsight.kind, LearningInsight.subject)
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(LearningInsight.kind == kind)
    return [_to_insight(i) for i in db.execute(stmt).scalars().all()]
