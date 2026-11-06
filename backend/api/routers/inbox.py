"""Inbox API (stage 5): real article list and KPIs, read-only (viewer)."""
from __future__ import annotations

from domains.inbox import service
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.errors import ApiError
from backend.api.pagination import MAX_PAGE_SIZE, page_params
from backend.database.session import get_db

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

SORTABLE = service.SORTABLE


class InboxItemRead(BaseModel):
    article_id: str
    title: str | None = None
    source_name: str | None = None
    priority: str | None = None
    domain: str | None = None
    analysis_status: str | None = None
    duplicate_cluster_id: str | None = None
    screening_status: str
    evidence_status: str | None = None
    retrieved_at: str | None = None
    review_required: bool = False


class InboxPageRead(BaseModel):
    items: list[InboxItemRead]
    total: int
    page: int
    page_size: int
    has_more: bool


@router.get("", response_model=InboxPageRead)
def inbox(
    q: str | None = Query(default=None, max_length=200),
    priority: str | None = Query(default=None, max_length=8),
    domain: str | None = Query(default=None, max_length=64),
    analysis_status: str | None = Query(default=None, max_length=32),
    dedup_state: str | None = Query(default=None, max_length=16),
    screening_status: str | None = Query(default=None, max_length=16),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    sort: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
) -> InboxPageRead:
    """فهرست صندوق اطلاعات با فیلتر/sort/صفحه‌بندی.

    پارامترهای نامعتبر مقدارها ۴۲۲ با پاکت خطای مرحلهٔ ۲ می‌دهند.
    """
    if dedup_state is not None and dedup_state not in ("duplicate", "unique"):
        raise ApiError(422, "VALIDATION_ERROR", "invalid dedup_state",
                       details={"fields": {"dedup_state": "must be duplicate or unique"}})
    if screening_status is not None and screening_status not in (
        "missing", "skipped", "pending", "failed", "relevant", "not_relevant"
    ):
        raise ApiError(422, "VALIDATION_ERROR", "invalid screening_status",
                       details={"fields": {"screening_status": "unknown value"}})
    params = page_params(page=page, page_size=page_size, sort=sort, sortable=SORTABLE)
    result = service.inbox_page(
        db, q=q, priority=priority, domain=domain, analysis_status=analysis_status,
        dedup_state=dedup_state, screening_status=screening_status,
        page=params.page, page_size=params.page_size,
        sort=(params.sort or "-retrieved_at"),
    )
    return InboxPageRead(**result)


@router.get("/summary")
def inbox_summary(db: Session = Depends(get_db)) -> dict:
    """KPIهای صندوق با تعریف صریح هر عدد."""
    return service.inbox_summary(db)
