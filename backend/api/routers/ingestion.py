"""Ingestion API (Phase 8) + مشاهده‌ی اسناد دریافت‌شده."""
from __future__ import annotations

import uuid

from domains.news.ingestion import NewsIngestionPipeline
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas.ingestion import (
    BotRunRead,
    BotRunRequest,
    DocumentRead,
    IngestJobRead,
    IngestRequest,
    IngestResultRead,
)
from backend.core.config import get_settings
from backend.database.models.document import Document
from backend.database.models.job import JobRun
from backend.database.models.source import Source
from backend.database.session import get_db

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


def _resolve_source(db: Session, source_id: str | None, source_name: str | None) -> Source:
    source: Source | None = None
    if source_id:
        try:
            source = db.get(Source, uuid.UUID(source_id))
        except ValueError:
            source = None
    elif source_name:
        source = db.execute(
            select(Source).where(Source.name == source_name)
        ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    return source


@router.post("", response_model=IngestResultRead)
async def ingest(payload: IngestRequest, db: Session = Depends(get_db)) -> IngestResultRead:
    """اجرای خط لوله‌ی دریافت برای یک منبع."""
    source = _resolve_source(db, payload.source_id, payload.source_name)
    pipeline = NewsIngestionPipeline(db)
    result = await pipeline.ingest_source_async(source, limit=payload.limit)
    return IngestResultRead(**result.as_dict())


@router.post("/all", response_model=list[IngestResultRead])
async def ingest_all(
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db),
    mock: bool | None = Query(default=None,
                              description="override دریافت: true=mock، false=واقعی، تهی=پیش‌فرض env"),
) -> list[IngestResultRead]:
    """اجرای دریافت برای منابع فعالی که روش rss و feed_url دارند.

    در MOCK_MODE همه‌ی منابع فعال با fetcher نمونه پردازش می‌شوند.
    در حالت واقعی فقط منابع news (rss با feed_url) انتخاب می‌شوند (P0-2).
    E2E FIND: زمان‌بند باید mock=false بدهد تا سند نمونه زیر نام واقعی نرود.
    """
    from domains.news.fetchers import MockFetcher, RSSFetcher

    from backend.core.mock_mode import effective_mock_mode

    use_mock = effective_mock_mode() if mock is None else mock
    stmt = select(Source).where(Source.active.is_(True))
    if not use_mock:
        stmt = stmt.where(Source.collection_method == "rss", Source.feed_url.is_not(None))
    sources = list(db.execute(stmt).scalars().all())

    if mock is None:
        pipeline = NewsIngestionPipeline(db)
    else:
        settings = get_settings()
        pipeline = NewsIngestionPipeline(
            db,
            fetcher=MockFetcher() if mock else RSSFetcher(
                timeout=float(settings.ai_request_timeout_seconds),
                user_agent=settings.user_agent,
            ),
        )
    results = []
    for source in sources:
        result = await pipeline.ingest_source_async(source, limit=limit)
        results.append(IngestResultRead(**result.as_dict()))
    return results


@router.post("/bot", response_model=BotRunRead)
async def run_bot(payload: BotRunRequest, db: Session = Depends(get_db)) -> BotRunRead:
    """اجرای کنترل‌شده‌ی Source Bot (تک‌منبع یا dueها).

    احراز هویت از include_router در main می‌آید. اجرای هم‌زمان دوم 409 می‌گیرد (قفل).
    فقط استخراج/dedup/اولویت؛ ذخیره‌سازی همان NewsIngestionPipeline است.
    """
    from source_bot.config import BotConfigError
    from source_bot.runner import run_once

    try:
        metrics = await run_once(source_name=payload.source_name,
                                 limit_sources=payload.limit,
                                 max_items_per_source=payload.max_items_per_source, db=db)
    except BotConfigError as exc:  # پیکربندی سرور نامعتبر است، نه درخواست کلاینت
        raise HTTPException(status_code=500,
                            detail=f"priority configuration invalid: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BotRunRead(**metrics.as_dict())


@router.post("/jobs", response_model=IngestJobRead, status_code=202)
def start_ingest_job(payload: BotRunRequest, background: BackgroundTasks,
                     db: Session = Depends(get_db)) -> IngestJobRead:
    """ثبت Job دریافت چندمنبعی در پس‌زمینه و بازگشت فوری شناسه (بدون انتظار برای دریافت)."""
    from source_bot.jobs import create_job, job_view, run_job

    try:
        spec: dict = {"source_name": payload.source_name, "limit": payload.limit}
        if payload.max_items_per_source is not None:  # کلید فقط وقتی اپراتور سقف خواسته
            spec["max_items_per_source"] = payload.max_items_per_source
        run = create_job(db, spec=spec)
    except RuntimeError as exc:  # یک Job فعال از قبل وجود دارد
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background.add_task(run_job, run.id)
    return IngestJobRead(**job_view(run))


@router.get("/jobs/{job_id}", response_model=IngestJobRead)
def get_ingest_job(job_id: str, db: Session = Depends(get_db)) -> IngestJobRead:
    """وضعیت و نتیجه‌ی Job دریافت (نتیجه پس از پایان از payload خوانده می‌شود)."""
    from source_bot.jobs import JOB_NAME, job_view

    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid job_id") from None
    run = db.get(JobRun, jid)
    if run is None or run.job_name != JOB_NAME:
        raise HTTPException(status_code=404, detail="job not found")
    return IngestJobRead(**job_view(run))


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    stmt = select(Document).order_by(Document.retrieved_at.desc().nullslast())
    if source_id:
        try:
            sid = uuid.UUID(source_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid source_id") from None
        stmt = stmt.where(Document.source_id == sid)
    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [
        DocumentRead(
            id=str(d.id),
            source_id=str(d.source_id) if d.source_id else None,
            url=d.url,
            title=d.title,
            language=d.language,
            author=d.author,
            published_at=d.published_at,
            retrieved_at=d.retrieved_at,
            content_hash=d.content_hash,
            ingestion_priority=d.ingestion_priority,
            priority_score=d.priority_score,
            priority_reason=d.priority_reason,
            priority_source=d.priority_source,
            priority_status=d.priority_status,
        )
        for d in rows
    ]
