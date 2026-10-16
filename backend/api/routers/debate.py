"""Debate Engine API (Step 3).

- POST /api/debate/run   → اجرای debate (بدون live=true واقعی اجرا نمی‌شود)
- GET  /api/debate/runs  → لیست اجراها
- GET  /api/debate/runs/{id} → جزئیات + پیام‌ها
- GET  /api/debate/scorecard → کارنامه‌ی صادقانه (Step 4)
"""
from __future__ import annotations

import asyncio
import uuid

from domains.debate.engine import DebateEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas.debate import (
    DebateMessageRead,
    DebateRunRead,
    DebateRunRequest,
    DebateRunResponse,
)
from backend.database.models.debate import DebateRun
from backend.database.session import get_db

router = APIRouter(prefix="/api/debate", tags=["debate"])


def _to_read(run: DebateRun) -> DebateRunRead:
    return DebateRunRead(
        id=str(run.id),
        target=run.target,
        target_date=run.target_date.isoformat() if run.target_date else None,
        horizon_days=run.horizon_days,
        status=run.status,
        context_hash=run.context_hash,
        reference_price=run.reference_price,
        consensus_probability=run.consensus_probability,
        disagreement=run.disagreement,
        total_tokens=run.total_tokens,
        total_cost_estimate=run.total_cost_estimate,
        messages=[
            DebateMessageRead(
                id=str(m.id), round_no=m.round_no, agent=m.agent,
                provider=m.provider, model=m.model,
                probability_up=m.probability_up, confidence=m.confidence,
                quality_score=m.quality_score, total_tokens=m.total_tokens,
                cost_estimate=m.cost_estimate, latency_ms=m.latency_ms,
                error=m.error,
            )
            for m in sorted(run.messages, key=lambda x: (x.round_no, x.agent))
        ],
    )


@router.post("/run", response_model=DebateRunResponse)
def run_debate(payload: DebateRunRequest, db: Session = Depends(get_db)) -> DebateRunResponse:
    if not payload.dry_run and not payload.live:
        raise HTTPException(
            status_code=422, detail="refusing real LLM calls without live=true"
        )
    engine = DebateEngine(db)
    outcome = asyncio.run(
        engine.run(
            target=payload.target, horizon_days=payload.horizon_days,
            dry_run=payload.dry_run, max_rounds=payload.max_rounds,
        )
    )
    return DebateRunResponse(
        run_id=outcome.run_id, status=outcome.status,
        consensus=outcome.consensus, disagreement=outcome.disagreement,
        confidence=outcome.confidence, forecast_ids=outcome.forecast_ids,
        total_tokens=outcome.total_tokens, total_cost=outcome.total_cost,
        errors=outcome.errors,
    )


@router.get("/runs", response_model=list[DebateRunRead])
def list_runs(
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)
) -> list[DebateRunRead]:
    from backend.database.models.debate import DebateRun as _R

    rows = db.execute(select(_R).order_by(_R.created_at.desc()).limit(limit)).scalars().all()
    out = []
    for r in rows:
        read = _to_read(r)
        read.messages = []
        out.append(read)
    return out


@router.get("/runs/{run_id}", response_model=DebateRunRead)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> DebateRunRead:
    run = db.get(DebateRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="debate run not found")
    return _to_read(run)


@router.get("/scorecard")
def get_scorecard(
    target: str | None = Query(default=None), db: Session = Depends(get_db)
) -> dict:
    from domains.debate.scorecard import ScorecardBuilder

    return ScorecardBuilder(db).build(target=target).as_dict()
