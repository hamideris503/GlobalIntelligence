"""Ingestion API (Phase 8) + مشاهده‌ی اسناد دریافت‌شده."""
from __future__ import annotations

import uuid

from domains.news.ingestion import NewsIngestionPipeline
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas.ingestion import (
    DocumentRead,
    IngestRequest,
    IngestResultRead,
)
from backend.database.models.document import Document
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
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)
) -> list[IngestResultRead]:
    """اجرای دریافت برای منابع فعالی که روش rss و feed_url دارند.

    در MOCK_MODE همه‌ی منابع فعال با fetcher نمونه پردازش می‌شوند.
    در حالت واقعی فقط منابع news (rss با feed_url) انتخاب می‌شوند (P0-2).
    """
    from backend.core.config import get_settings

    stmt = select(Source).where(Source.active.is_(True))
    if not get_settings().mock_mode:
        stmt = stmt.where(Source.collection_method == "rss", Source.feed_url.is_not(None))
    sources = list(db.execute(stmt).scalars().all())

    pipeline = NewsIngestionPipeline(db)
    results = []
    for source in sources:
        result = await pipeline.ingest_source_async(source, limit=limit)
        results.append(IngestResultRead(**result.as_dict()))
    return results


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
        )
        for d in rows
    ]
