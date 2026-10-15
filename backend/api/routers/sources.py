"""Sources Registry API (بند 17).

CRUD روی رجیستری منابع + فعال/غیرفعال‌سازی + ثبت سلامت.
"""
from __future__ import annotations

import uuid

from domains.news.source_registry import SourceRegistry
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
        feed_url=s.feed_url,
        homepage_url=s.homepage_url,
        canonical_url=s.canonical_url,
        geography=s.geography,
        category=s.category,
        subcategory=s.subcategory,
        primary_or_secondary=s.primary_or_secondary,
        official_status=s.official_status,
        reliability_rationale=s.reliability_rationale,
        bias_notes=s.bias_notes,
        priority=s.priority,
        access_model=s.access_model,
        registration_required=s.registration_required,
        api_url=s.api_url,
        api_documentation_url=s.api_documentation_url,
        api_auth_type=s.api_auth_type,
        rss_url=s.rss_url,
        sitemap_url=s.sitemap_url,
        archive_url=s.archive_url,
        data_download_url=s.data_download_url,
        terms_url=s.terms_url,
        license_terms=s.license_terms,
        robots_status=s.robots_status,
        validation_status=s.validation_status or "PENDING_VALIDATION",
        last_checked_at=s.last_checked_at,
    )


@router.get("", response_model=list[SourceRead])
def list_sources(
    active: bool | None = None,
    country: str | None = None,
    source_type: str | None = Query(default=None, alias="type"),
    category: str | None = None,
    validation_status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SourceRead]:
    reg = SourceRegistry(db)
    rows = reg.list(
        active=active, country=country, source_type=source_type, limit=5000, offset=0
    )
    if category:
        rows = [s for s in rows if (s.category or "") == category]
    if validation_status:
        rows = [s for s in rows if (s.validation_status or "") == validation_status]
    return [_to_read(s) for s in rows[offset : offset + limit]]


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


@router.post("/{source_id}/recheck", response_model=SourceRead)
def recheck_source(source_id: uuid.UUID, db: Session = Depends(get_db)) -> SourceRead:
    """بررسی مجدد زنده‌ی homepage منبع و به‌روزرسانی وضعیت (census)."""
    from datetime import UTC, datetime

    from domains.news.source_verify import fetch_url

    source = SourceRegistry(db).get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    if not source.homepage_url:
        raise HTTPException(status_code=422, detail="source has no homepage_url")
    res = fetch_url(source.homepage_url, timeout=25.0)
    source.last_checked_at = datetime.now(UTC)
    if res.ok and res.final_url:
        source.canonical_url = res.final_url
        source.validation_status = "VERIFIED"
        source.last_error = None
    else:
        mapping = {"blocked": "NEEDS_REVIEW", "http_404": "NEEDS_REVIEW",
                   "http_4xx": "NEEDS_REVIEW", "http_5xx": "TEMPORARILY_UNAVAILABLE",
                   "timeout": "TEMPORARILY_UNAVAILABLE", "dns_or_connect": "NEEDS_REVIEW",
                   "ssrf_blocked": "INVALID_URL", "invalid_url": "INVALID_URL",
                   "too_big": "VERIFIED"}
        source.validation_status = mapping.get(res.error_kind or "", "NEEDS_REVIEW")
        source.last_error = f"{res.error_kind} @ {res.final_url or source.homepage_url}"[:500]
    db.commit()
    db.refresh(source)
    from domains.audit.service import log_action

    log_action(db, action="source_recheck", actor="api", target_type="source",
               target_id=str(source_id),
               result={"validation_status": source.validation_status})
    return _to_read(source)


@router.get("/export/all")
def export_sources(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """خروجی CSV/JSON رجیستری (census؛ بدون هیچ secret — رجیستری secret ندارد)."""
    import csv
    import io

    from fastapi.responses import PlainTextResponse

    rows = SourceRegistry(db).list(limit=5000)
    cols = ["name", "homepage_url", "canonical_url", "domain", "country",
            "language", "category", "subcategory", "type", "validation_status",
            "api_url", "rss_url", "access_model", "active", "last_checked_at"]
    data = [{c: getattr(s, c, None) for c in cols} for s in rows]
    for d in data:
        if d.get("last_checked_at") is not None:
            d["last_checked_at"] = str(d["last_checked_at"])
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols)
        writer.writeheader()
        writer.writerows(data)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    from fastapi.responses import JSONResponse

    return JSONResponse(data)
