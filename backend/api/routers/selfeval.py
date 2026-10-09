"""Self Evaluation API (Phase 39).

- POST /api/self-eval/run → اجرای خودارزیابی و ثبت تاریخچه
- GET  /api/self-eval/latest → آخرین خودارزیابی
- GET  /api/self-eval/history → تاریخچه‌ی نمرات
"""
from __future__ import annotations

import json

from domains.selfeval.service import SelfEvaluationService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.self_evaluation import SelfEvaluation
from backend.database.session import get_db

router = APIRouter(prefix="/api/self-eval", tags=["self-eval"])


class SelfEvalOutcomeRead(BaseModel):
    evaluation_id: str
    score: float
    grade: str
    checks: list[dict]


class SelfEvalRead(BaseModel):
    id: str
    score: float | None
    grade: str | None
    checks: list[dict]
    observed_at: str | None


def _to_eval(e: SelfEvaluation) -> SelfEvalRead:
    try:
        checks = json.loads(e.checks or "[]")
    except Exception:  # noqa: BLE001
        checks = []
    return SelfEvalRead(
        id=str(e.id),
        score=e.score,
        grade=e.grade,
        checks=checks if isinstance(checks, list) else [],
        observed_at=e.observed_at.isoformat() if e.observed_at else None,
    )


@router.post("/run", response_model=SelfEvalOutcomeRead)
def run_self_eval(db: Session = Depends(get_db)) -> SelfEvalOutcomeRead:
    """اجرای خودارزیابی پلتفرم و ثبت در تاریخچه."""
    outcome = SelfEvaluationService(db).run()
    return SelfEvalOutcomeRead(**outcome.as_dict())


@router.get("/latest", response_model=SelfEvalRead)
def latest(db: Session = Depends(get_db)) -> SelfEvalRead:
    stmt = select(SelfEvaluation).order_by(SelfEvaluation.created_at.desc()).limit(1)
    record = db.execute(stmt).scalars().first()
    if record is None:
        raise HTTPException(status_code=404, detail="no self-evaluation yet")
    return _to_eval(record)


@router.get("/history", response_model=list[SelfEvalRead])
def history(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> list[SelfEvalRead]:
    stmt = (
        select(SelfEvaluation).order_by(SelfEvaluation.created_at.desc()).limit(limit)
    )
    return [_to_eval(e) for e in db.execute(stmt).scalars().all()]
