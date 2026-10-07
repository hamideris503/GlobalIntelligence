"""Deduplication API (Phase 9)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db
from domains.news.dedup_service import DedupService

router = APIRouter(prefix="/api/dedup", tags=["dedup"])


class DedupSummary(BaseModel):
    documents: int
    clusters_total: int
    duplicate_clusters: int
    exact_pairs: int
    near_pairs: int
    repost_pairs: int
    updated: int


@router.post("/run", response_model=DedupSummary)
def run_dedup(
    limit: int = Query(default=500, ge=1, le=5000),
    near_threshold: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> DedupSummary:
    """اجرای خوشه‌بندی تکراری‌ها روی اسناد ذخیره‌شده."""
    summary = DedupService(db).run(limit=limit, near_threshold=near_threshold)
    return DedupSummary(**summary)
