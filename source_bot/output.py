"""Output — تحویل به pipeline موجود؛ آداپتورها مستقیم DB نمی‌نویسند.

اولویت دریافت (ingestion_priority) با Article.importance تحلیلی قاطی نمی‌شود:
اولویت فقط در doc_metadata + ستون‌های جدید documents ذخیره می‌شود.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline


def deliver(
    db: Session, source: Source, item: RawItem, *,
    priority: str, score: float, reason: str,
    priority_source: str, priority_status: str,
    duplicate_status: str, canonical_url: str | None = None,
    final_url: str | None = None, external_id: str | None = None,
) -> bool:
    meta = dict(item.metadata or {})
    meta.update({
        "ingestion_priority": priority,
        "priority_score": score,
        "priority_reason": reason,
        "priority_source": priority_source,
        "priority_status": priority_status,
        "duplicate_status": duplicate_status,
        "canonical_url": canonical_url,
        "final_url": final_url,
        "external_id": external_id,
    })
    enriched = RawItem(
        title=item.title, url=item.url, raw_text=item.raw_text,
        published_at=item.published_at, author=item.author,
        language=item.language, raw_payload=item.raw_payload, metadata=meta,
    )
    pipeline = NewsIngestionPipeline(db)
    from datetime import UTC, datetime

    before = datetime.now(UTC)
    with db.begin_nested():
        stored = pipeline.store_item(source, enriched)
    if stored:
        # ستون‌های اولویت روی همان رکورد تازه‌ساخته‌شده (شناسایی دقیق، نه latest).
        # content_hash تهی با `= NULL` هرگز match نمی‌شود؛ پس برای آن حالت،
        # فقط ردیف‌های ساخته‌شده پس از شروع همین deliver کاندید‌اند.
        # کل بلاک در savepoint تودرتوست: شکست ستون‌گذاری به savepoint برمی‌گردد،
        # ردیف ذخیره‌شده سالم می‌ماند و session برای آیتم‌های بعدی قابل‌استفاده است.
        try:
            with db.begin_nested():
                doc, status = _find_created_row(db, source, item, before)
                if doc is None:
                    from backend.core.logging import get_logger as _gl

                    _gl(__name__).warning(
                        "priority columns skipped: %s | source=%s url=%s",
                        status, source.name, item.url,
                    )
                else:
                    for col, val in (
                        ("ingestion_priority", priority), ("priority_score", score),
                        ("priority_reason", reason[:500]), ("priority_source", priority_source),
                        ("priority_status", priority_status), ("duplicate_status", duplicate_status),
                        ("canonical_url", canonical_url), ("final_url", final_url),
                        ("external_id", external_id),
                    ):
                        if hasattr(doc, col):
                            setattr(doc, col, val)
                    db.flush()
        except Exception as exc:  # noqa: BLE001
            from backend.core.logging import get_logger as _gl

            _gl(__name__).warning(
                "priority columns skipped | source=%s url=%s err=%s",
                source.name, item.url, type(exc).__name__,
            )
    db.commit()
    return stored


def _find_created_row(db: Session, source: Source, item: RawItem, before) -> tuple[Document | None, str]:
    """ردیف ساخته‌شده در همین deliver را دقیق پیدا می‌کند.

    برمی‌گرداند (doc_or_None, status) با status یکی از:
    found | not_found | no_key | ambiguous.

    هش‌ها از مقادیر نرمال‌شده محاسبه می‌شوند (همان‌چه store_item ذخیره کرد)،
    نه از raw — وگرنه تگ/متن دارای HTML با cleaned متفاوت می‌شود.
    - content معتبر: همان کلید یکتای pipeline (بدون تغییر رفتار dedup).
    - content تهی: فقط کاندیدهای هم‌URL که پس از `before` ساخته شده‌اند؛
      اگر دقیقاً یکی بود همان است، وگرنه ambiguous (بدون نوشتن).
    """
    from domains.news.normalizer import normalize

    norm = normalize(item)
    uh, ch = norm.hash, norm.content_hash
    if ch is not None:
        doc = (
            db.query(Document)
            .filter(
                Document.source_id == source.id,
                Document.hash == uh,
                Document.content_hash == ch,
            )
            .order_by(Document.retrieved_at.desc())
            .first()
        )
        return (doc, "found" if doc is not None else "not_found")
    if uh is None:
        return (None, "no_key")
    cands = (
        db.query(Document)
        .filter(
            Document.source_id == source.id,
            Document.hash == uh,
            Document.content_hash.is_(None),
            Document.retrieved_at >= before,
        )
        .all()
    )
    if len(cands) == 1:
        return (cands[0], "found")
    return (None, "ambiguous")


def attach_priority(db: Session, document: Document, *, priority: str, score: float,
                    reason: str, priority_source: str, priority_status: str) -> None:
    """قرارداد مشترک برای موتورهای تخصصی (macro/market): بدون استخراج موازی،
    اولویت/وضعیت را روی Document موجود می‌نشانند (همان ستون‌ها + metadata)."""
    import json as _json

    try:
        meta = _json.loads(document.doc_metadata) if document.doc_metadata else {}
    except Exception:  # noqa: BLE001
        meta = {}
    meta.update({
        "ingestion_priority": priority, "priority_score": score,
        "priority_reason": reason, "priority_source": priority_source,
        "priority_status": priority_status,
    })
    document.doc_metadata = _json.dumps(meta, ensure_ascii=False, default=str)
    for col, val in (("ingestion_priority", priority), ("priority_score", score),
                     ("priority_reason", reason[:500]), ("priority_source", priority_source),
                     ("priority_status", priority_status)):
        if hasattr(document, col):
            setattr(document, col, val)
    db.flush()


def merge_priority_metadata(existing_json: str | None, patch: dict) -> str:
    try:
        base = json.loads(existing_json) if existing_json else {}
    except Exception:  # noqa: BLE001
        base = {}
    base.update(patch)
    return json.dumps(base, ensure_ascii=False, default=str)
