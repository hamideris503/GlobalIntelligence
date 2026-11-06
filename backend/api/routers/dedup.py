"""Deduplication API (Phase 9)."""
from __future__ import annotations

import json

from domains.news.dedup_service import DedupService
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/dedup", tags=["dedup"])


class DedupSummary(BaseModel):
    documents: int
    clusters_total: int
    duplicate_clusters: int
    exact_pairs: int
    near_pairs: int
    repost_pairs: int
    updated: int


@router.get("/clusters")
def list_clusters(
    cluster: str | None = Query(default=None, max_length=128),
    limit: int | None = Query(default=None, ge=1, le=20000),
    db: Session = Depends(get_db),
) -> list[dict]:
    """خوشه‌های تشخیص‌داده‌شده (F12.1.1).

    با `cluster` فقط همان خوشه برمی‌گردد (فیلتر سمت سرور، بدون بارگذاری کل جدول).
    بدون پارامتر رفتار قبلی حفظ می‌شود؛ `limit` فقط برای مهار است.
    """
    from sqlalchemy import or_
    from sqlalchemy.orm import selectinload

    from backend.database.models.article import Article
    from backend.database.models.document import Document

    stmt = select(Article).options(selectinload(Article.document))
    if cluster:
        # خوشه‌ی قدیمی فقط در doc_metadata ثبت شده بود؛ هر دو محل بررسی می‌شود.
        # LIKE فقط prefilter است و تطابق نهایی در _cluster_of انجام می‌شود.
        stmt = stmt.outerjoin(Document, Article.document_id == Document.id).where(
            or_(
                Article.duplicate_cluster == cluster,
                Document.doc_metadata.like(_meta_pattern(cluster), escape="\\"),
            )
        )
    if limit:
        stmt = stmt.limit(limit)
    rows = db.execute(stmt).scalars().all()
    out = []
    for a in rows:
        value = _cluster_of(a)
        if cluster and value != cluster:
            continue  # prefilter باعت آوردن مقدارهای شبیه می‌شود؛ اینجا حذف می‌گردند
        out.append({"article_id": str(a.id), "document_id": str(a.document_id) if a.document_id else None,
                    "source_id": str(a.document.source_id) if a.document and a.document.source_id else None,
                    "cluster": value})
    return out


def _meta_pattern(cluster: str) -> str:
    """الگوی LIKE با escape کاراکترهای ویژه؛ مقدار مستقیم داخل SQL نمی‌رود."""
    escaped = cluster.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f'%"{escaped}"%'


def _cluster_of(article) -> str | None:  # noqa: ANN001
    """خوشهٔ موثر مقاله: ستون، سپس fallback متادیتای سند (سازگاری دادهٔ قدیمی)."""
    cluster = article.duplicate_cluster
    if cluster is None and article.document is not None:
        try:
            meta = json.loads(article.document.doc_metadata) if article.document.doc_metadata else {}
            cluster = meta.get("dedup_cluster")
        except Exception:  # noqa: BLE001
            cluster = None
    return cluster


@router.post("/run", response_model=DedupSummary)
def run_dedup(
    limit: int = Query(default=500, ge=1, le=5000),
    near_threshold: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> DedupSummary:
    """اجرای خوشه‌بندی تکراری‌ها روی اسناد ذخیره‌شده."""
    summary = DedupService(db).run(limit=limit, near_threshold=near_threshold)
    return DedupSummary(**summary)
