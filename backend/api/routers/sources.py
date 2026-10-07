"""Sources Registry API (بند 17).

CRUD روی رجیستری منابع + فعال/غیرفعال‌سازی + ثبت سلامت.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.schemas.sources import (
    SourceCreate,
    SourceHealthUpdate,
    SourceRead,
    SourceUpdate,
)
from backend.database.models.source import Source
from backend.database.session import get_db
from domains.news.source_registry import SourceRegistry

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _to_read(s: Source) -> SourceRead:
    return SourceRead(
        id=str(s.id),
        name=s.name,
        domain=s.domain,
        country=s.country,
        type=s.type.value if hasattr(s.type, "value") else str(s.type),
        language=s.language,
        credibility_score=s.credibility_score,
        historical_accuracy=s.historical_accuracy,
        correction_rate=s.correction_rate,
        independence_score=s.independence_score,
        primary_source_ratio=s.primary_source_ratio,
        latency_seconds=s.latency_seconds,
        license=s.license,
        terms=s.terms,
        collection_method=s.collection_method,
        active=s.active,
        last_success=s.last_success,
        last_error=s.last_error,
    )


@router.get("", response_model=list[SourceRead])
def list_sources(
    active: bool | None = None,
    country: str | None = None,
    source_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SourceRead]:
    reg = SourceRegistry(db)
    return [
        _to_read(s)
        for s in reg.list(
            active=active, country=country, source_type=source_type, limit=limit, offset=offset
        )
    ]


@router.post("", response_model=SourceRead, status_code=201)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> SourceRead:
    reg = SourceRegistry(db)
    if reg.get_by_name(payload.name):
        raise HTTPException(status_code=409, detail="source with this name already exists")
    source = reg.create(**payload.model_dump())
    return _to_read(source)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)) -> SourceRead:
    source = SourceRegistry(db).get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    return _to_read(source)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: uuid.UUID, payload: SourceUpdate, db: Session = Depends(get_db)
) -> SourceRead:
    reg = SourceRegistry(db)
    source = reg.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    reg.update(source, **payload.model_dump(exclude_unset=True))
    return _to_read(source)


@router.post("/{source_id}/health", response_model=SourceRead)
def record_health(
    source_id: uuid.UUID, payload: SourceHealthUpdate, db: Session = Depends(get_db)
) -> SourceRead:
    reg = SourceRegistry(db)
    source = reg.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    if payload.ok:
        reg.record_success(source)
    else:
        reg.record_error(source, payload.error or "unknown error")
    return _to_read(source)
