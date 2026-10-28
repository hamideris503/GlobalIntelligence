"""Document — نسخه‌ی خام و اصلی یک محتوا (بند 19 و 20).

- `raw_payload`: نسخه‌ی اصلی و دست‌نخورده‌ی آیتم (XML/JSON) — بند 19.
- `raw_text`: متن پاک‌سازی‌شده‌ی قابل جستجو (بعد از حذف HTML).
- یکتایی URL‌دار درون یک منبع: (source_id, hash, content_hash).
- یکتایی ردیف بدون URL درون یک منبع: (source_id, external_id) با index جزئی.
- یکتایی محتوای بدون URL (بدون external_id معتبر): (source_id, content_hash) با index جزئی.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Collection
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

Provenance = Literal["mock", "real", "unknown"]

# هویت ردیف‌های بدون URL: (source_id, external_id) — index جزئی، چون NULL در
# SQLite/PostgreSQL یکتایی را نمی‌شکند و ردیف‌های URL‌دار نباید تغییر کنند.
_RIDLESS_IDENTITY_WHERE = "external_id IS NOT NULL AND hash IS NULL"

# هویت محتوایی ردیف‌های بدون URL و بدون external_id معتبر: (source_id, content_hash).
# `UniqueConstraint(source_id, hash, content_hash)` برای این ردیف‌ها بی‌اثر است چون
# NULL در SQL متمایز شمرده می‌شود؛ پس تضمین یکتایی به همین index جزئی نیاز دارد.
# `trim` عمدی است: external_id خالی/فاصله‌دار شناسه‌ی معتبر نیست و نباید ردیف را از
# این index بیرون بیندازد.
_RIDLESS_CONTENT_WHERE = (
    "hash IS NULL AND content_hash IS NOT NULL "
    "AND (external_id IS NULL OR trim(external_id) = '')"
)


def provenance_of(doc_metadata: str | None) -> Provenance:
    """منشأ رکورد از روی metadata — سه‌حالته‌ی صریح.

    فقط `mock: true` بولی معتبر → "mock"؛ `mock: false` صریح → "real"؛
    هر چیز دیگر (تهی/None/JSON خراب/ساختار غیرمنتظره) → "unknown".
    unknown هرگز مدرک real بودن نیست. رکورد را تغییر نمی‌دهد.
    """
    if not isinstance(doc_metadata, str) or not doc_metadata.strip():
        return "unknown"
    try:
        data = json.loads(doc_metadata)
    except Exception:  # noqa: BLE001
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    flag = data.get("mock", None)
    if flag is True:
        return "mock"
    if flag is False:
        return "real"
    return "unknown"


def is_mock_record(doc_metadata: str | None) -> bool:
    """True فقط برای رکورد صریحاً mock — برای unknown هرگز True نیست."""
    return provenance_of(doc_metadata) == "mock"


def mock_document_ids(db: Session, doc_ids: Collection) -> set:
    """زیرمجموعه‌ی mock از شناسه‌ها با یک کوئری (برای guardها)."""
    ids = [i for i in set(doc_ids) if i is not None]
    if not ids:
        return set()
    rows = db.execute(
        select(Document.id, Document.doc_metadata).where(Document.id.in_(ids))
    ).all()
    return {doc_id for doc_id, meta in rows if is_mock_record(meta)}


def events_with_mock_articles(db: Session, event_ids: Collection) -> set:
    """رویدادهایی که حداقل یک مقاله‌ی صریحاً mock دارند (یک کوئری)."""
    from backend.database.models.article import Article

    eids = [i for i in set(event_ids) if i is not None]
    if not eids:
        return set()
    rows = (
        db.execute(
            select(Article.event_id, Document.doc_metadata)
            .join(Document, Document.id == Article.document_id)
            .where(Article.event_id.in_(eids))
        ).all()
    )
    flagged: set = set()
    for event_id, meta in rows:
        if is_mock_record(meta):
            flagged.add(event_id)
    return flagged


class Document(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "hash", "content_hash", name="uq_document_source_url_content"),
        Index(
            "uq_documents_source_external_id",
            "source_id",
            "external_id",
            unique=True,
            sqlite_where=text(_RIDLESS_IDENTITY_WHERE),
            postgresql_where=text(_RIDLESS_IDENTITY_WHERE),
        ),
        Index(
            "uq_documents_source_content_hash_ridless",
            "source_id",
            "content_hash",
            unique=True,
            sqlite_where=text(_RIDLESS_CONTENT_WHERE),
            postgresql_where=text(_RIDLESS_CONTENT_WHERE),
        ),
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[str | None] = mapped_column(Text)  # نسخه‌ی اصلی خام
    raw_text: Mapped[str | None] = mapped_column(Text)      # متن پاک‌شده
    language: Mapped[str | None] = mapped_column(String(16))
    author: Mapped[str | None] = mapped_column(String(255))
    revision: Mapped[int | None] = mapped_column(Integer)

    hash: Mapped[str | None] = mapped_column(String(128), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)

    license: Mapped[str | None] = mapped_column(String(255))
    terms: Mapped[str | None] = mapped_column(Text)
    doc_metadata: Mapped[str | None] = mapped_column(Text)  # JSON (stringified)

    # --- source_bot: اولویت دریافت (جدا از Article.importance تحلیلی) ---
    canonical_url: Mapped[str | None] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    ingestion_priority: Mapped[str | None] = mapped_column(String(8), index=True)
    priority_score: Mapped[float | None] = mapped_column(Float)
    priority_reason: Mapped[str | None] = mapped_column(Text)
    priority_source: Mapped[str | None] = mapped_column(String(16))
    priority_status: Mapped[str | None] = mapped_column(String(32))
    duplicate_status: Mapped[str | None] = mapped_column(String(32))
    canonical_id: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source | None] = relationship(lazy="selectin")  # noqa: F821
    articles: Mapped[list[Article]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
