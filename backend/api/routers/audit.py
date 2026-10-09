"""Audit / Replay API (Phase 38).

- POST /api/audit/log      → ثبت دستی یک اقدام
- GET  /api/audit/records   → لیست لاگ (فیلتر action)
- POST /api/audit/replay   → بازپخش یک موتور + گزارش تطابق
- GET  /api/audit/engines   → موتورهای قابل بازپخش
"""
from __future__ import annotations

from domains.audit.replay import SUPPORTED_ENGINES, replay
from domains.audit.service import log_action
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.audit_record import AuditRecord
from backend.database.session import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])


class LogRequest(BaseModel):
    action: str
    actor: str = "api"
    target_type: str | None = None
    target_id: str | None = None
    params: dict = {}
    result: dict = {}
    status: str = "ok"


class LogRead(BaseModel):
    id: str
    action: str
    actor: str
    target_type: str | None
    target_id: str | None
    params: dict
    result: dict
    status: str
    observed_at: str | None


class ReplayOutcomeRead(BaseModel):
    engine: str
    match: bool
    digest_before: str
    digest_after: str
    rows: int
    errors: list[str]


def _parse_json(raw: str | None) -> dict:
    import json

    try:
        out = json.loads(raw or "{}")
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _to_log(r: AuditRecord) -> LogRead:
    return LogRead(
        id=str(r.id),
        action=r.action,
        actor=r.actor,
        target_type=r.target_type,
        target_id=r.target_id,
        params=_parse_json(r.params),
        result=_parse_json(r.result),
        status=r.status,
        observed_at=r.observed_at.isoformat() if r.observed_at else None,
    )


@router.post("/log", response_model=LogRead)
def create_log(req: LogRequest, db: Session = Depends(get_db)) -> LogRead:
    if not req.action.strip():
        raise HTTPException(status_code=422, detail="action must not be empty")
    record = log_action(
        db,
        action=req.action.strip(),
        actor=req.actor,
        target_type=req.target_type,
        target_id=req.target_id,
        params=req.params,
        result=req.result,
        status=req.status,
    )
    return _to_log(record)


@router.get("/records", response_model=list[LogRead])
def list_records(
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[LogRead]:
    stmt = select(AuditRecord).order_by(AuditRecord.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditRecord.action == action)
    return [_to_log(r) for r in db.execute(stmt).scalars().all()]


@router.post("/replay", response_model=ReplayOutcomeRead)
def replay_engine(
    engine: str = Query(...), db: Session = Depends(get_db)
) -> ReplayOutcomeRead:
    """بازپخش یک موتور و گزارش تطابق fingerprint."""
    if engine not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported engine; choose from {sorted(SUPPORTED_ENGINES)}",
        )
    outcome = replay(db, engine)
    try:
        log_action(
            db,
            action="audit.replay",
            target_type="engine",
            target_id=engine,
            params={},
            result=outcome.as_dict(),
            status="ok" if outcome.match else "mismatch",
        )
    except Exception:  # noqa: BLE001
        pass
    return ReplayOutcomeRead(**outcome.as_dict())


@router.get("/engines")
def supported_engines() -> dict:
    return {"engines": sorted(SUPPORTED_ENGINES)}
