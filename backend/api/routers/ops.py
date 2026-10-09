"""Ops status API (Phase 49).

- GET /api/ops/status → تصویر لحظه‌ای سلامت ops: دیتابیس، شمارش‌ها،
  آخرین jobها، آخرین خودارزیابی، هشدارهای فعال، آخرین جهان.
فقط خواندنی؛ بدون migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models.alert import Alert
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.job import JobRun
from backend.database.models.self_evaluation import SelfEvaluation
from backend.database.models.source import Source
from backend.database.models.world_state import WorldState
from backend.database.session import get_db

router = APIRouter(prefix="/api/ops", tags=["ops"])


class OpsStatusRead(BaseModel):
    database_ok: bool
    counts: dict[str, int]
    last_jobs: list[dict]
    latest_self_eval: dict
    active_alerts: int
    latest_world_state: dict


@router.get("/status", response_model=OpsStatusRead)
def ops_status(db: Session = Depends(get_db)) -> OpsStatusRead:
    """وضعیت لحظه‌ای ops برای مانیتورینگ ۲۴/۷."""
    try:
        db.execute(select(1))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    counts = {}
    for name, model in [
        ("sources", Source),
        ("documents", Document),
        ("articles", Article),
        ("events", Event),
        ("alerts", Alert),
    ]:
        try:
            counts[name] = int(
                db.execute(select(func.count()).select_from(model)).scalars().one() or 0
            )
        except Exception:  # noqa: BLE001
            counts[name] = -1

    last_jobs = []
    try:
        for job in db.execute(
            select(JobRun).order_by(JobRun.created_at.desc()).limit(5)
        ).scalars().all():
            last_jobs.append(
                {
                    "job_name": job.job_name,
                    "status": job.status,
                    "source": job.source,
                }
            )
    except Exception:  # noqa: BLE001
        pass

    latest_eval: dict = {}
    try:
        row = db.execute(
            select(SelfEvaluation).order_by(SelfEvaluation.created_at.desc()).limit(1)
        ).scalars().first()
        if row is not None:
            latest_eval = {"score": row.score, "grade": row.grade}
    except Exception:  # noqa: BLE001
        pass

    active_alerts = 0
    try:
        active_alerts = int(
            db.execute(
                select(func.count())
                .select_from(Alert)
                .where(Alert.status == "active")
            ).scalars().one() or 0
        )
    except Exception:  # noqa: BLE001
        pass

    latest_ws: dict = {}
    try:
        ws = db.execute(
            select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        ).scalars().first()
        if ws is not None:
            latest_ws = {
                "macro_regime": ws.macro_regime,
                "market_regime": ws.market_regime,
            }
    except Exception:  # noqa: BLE001
        pass

    return OpsStatusRead(
        database_ok=db_ok,
        counts=counts,
        last_jobs=last_jobs,
        latest_self_eval=latest_eval,
        active_alerts=active_alerts,
        latest_world_state=latest_ws,
    )
