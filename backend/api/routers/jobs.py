"""Jobs API — نقطه‌ی ورود orchestration (n8n → backend → database).

Phase 4: n8n یک درخواست به `/api/jobs/trigger` می‌زند؛ backend رکورد JobRun
را در PostgreSQL ذخیره می‌کند و لیست آخرین اجراها را برمی‌گرداند.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas.jobs import (
    JobRunRead,
    JobTriggerRequest,
    JobTriggerResponse,
)
from backend.core.logging import get_logger
from backend.database.models.job import JobRun
from backend.database.session import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/trigger", response_model=JobTriggerResponse, status_code=201)
def trigger_job(
    payload: JobTriggerRequest, db: Session = Depends(get_db)
) -> JobTriggerResponse:
    """ثبت یک اجرای job (مثلاً از n8n یا worker)."""
    run = JobRun(
        job_name=payload.job_name,
        source=payload.source,
        status="received",
        payload=json.dumps(payload.payload, ensure_ascii=False) if payload.payload else None,
        message="job accepted",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("job triggered | name=%s source=%s id=%s", run.job_name, run.source, run.id)

    return JobTriggerResponse(
        status="accepted",
        job_run=JobRunRead(
            id=str(run.id),
            job_name=run.job_name,
            source=run.source,
            status=run.status,
            message=run.message,
            started_at=run.started_at,
        ),
    )


@router.get("", response_model=list[JobRunRead])
def list_jobs(
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)
) -> list[JobRunRead]:
    """آخرین اجراهای job."""
    rows = db.execute(select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)).scalars().all()
    return [
        JobRunRead(
            id=str(r.id),
            job_name=r.job_name,
            source=r.source,
            status=r.status,
            message=r.message,
            started_at=r.started_at,
        )
        for r in rows
    ]
