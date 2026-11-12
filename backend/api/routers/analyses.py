"""Analyses API (مرحلهٔ ۶A) — نمای تجمیعی تحلیل‌ها.

- GET  /api/analyses           فهرست تحلیل‌ها (Recommendation/Debate/Forecast)
- GET  /api/analyses/{id}/trace زنجیرهٔ قابل‌ردیابی
- POST /api/analyses/request    درخواست اجرای تحلیل از مسیر dispatch موجود
"""
from __future__ import annotations

from typing import Literal

from domains.analyses import service
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.errors import ApiError
from backend.api.pagination import MAX_PAGE_SIZE, page_params
from backend.database.session import get_db

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

SORTABLE = service._SORTABLE


class AnalysisRead(BaseModel):
    id: str
    kind: str
    raw_id: str
    title: str | None = None
    domain: str | None = None
    status: str
    model: str | None = None
    provider: str | None = None
    confidence: float | None = None
    priority: int | None = None
    summary: str | None = None
    created_at: str | None = None
    evidence_status: str


class AnalysisPageRead(BaseModel):
    items: list[AnalysisRead]
    total: int
    page: int
    page_size: int
    has_more: bool


@router.get("", response_model=AnalysisPageRead)
def list_analyses(
    domain: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=32),
    model: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=200),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    sort: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
) -> AnalysisPageRead:
    params = page_params(page=page, page_size=page_size, sort=sort, sortable=SORTABLE)
    result = service.listing(
        db, domain=domain, status=status, model=model, q=q,
        page=params.page, page_size=params.page_size,
        sort=(params.sort or "-created_at"),
    )
    return AnalysisPageRead(**result)


@router.get("/{analysis_id}/trace")
def analysis_trace(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    result = service.trace(db, analysis_id)
    if result is None:
        raise ApiError(404, "NOT_FOUND", "analysis not found")
    return result


class AnalysisRequest(BaseModel):
    task: Literal[
        "event_extraction", "claim_extraction", "graph_extraction",
        "evidence_collection", "domain_geopolitics", "domain_society",
        "claim_independence",
    ] = "evidence_collection"
    limit: int = 20


class AnalysisRequestResult(BaseModel):
    accepted: bool
    task: str
    processed: int
    outcome: dict
    requested_at: str


@router.post("/request", response_model=AnalysisRequestResult)
async def request_analysis(
    payload: AnalysisRequest, db: Session = Depends(get_db)
) -> AnalysisRequestResult:
    """درخواست اجرای تحلیل از مسیر dispatch موجود (بدون فراخوانی مستقیم LLM).

    یک batch از task موجود را روی صف dispatch اجرا می‌کند و خلاصهٔ outcome را
    برمی‌گرداند. اگر هیچ کار واجدشرطی نباشد، `processed=0` صادقانه برمی‌گردد.
    """
    from datetime import UTC, datetime

    from backend.ai.dispatch.runner import run_once

    limit = max(1, min(payload.limit, 100))
    outcome = await run_once(db, limit=limit, task=payload.task)
    return AnalysisRequestResult(
        accepted=True,
        task=payload.task,
        processed=(outcome.completed + outcome.retryable + outcome.terminal),
        outcome=outcome.as_dict(),
        requested_at=datetime.now(UTC).isoformat(),
    )
