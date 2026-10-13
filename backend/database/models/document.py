"""Document — نسخه‌ی خام و اصلی یک محتوا (بند 19 و 20).

- `raw_payload`: نسخه‌ی اصلی و دست‌نخورده‌ی آیتم (XML/JSON) — بند 19.
- `raw_text`: متن پاک‌سازی‌شده‌ی قابل جستجو (بعد از حذف HTML).
- یکتایی فقط درون یک منبع: (source_id, hash, content_hash).
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin


class Document(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "hash", "content_hash", name="uq_document_source_url_content"),
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
