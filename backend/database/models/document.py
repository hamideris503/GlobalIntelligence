"""Document — نسخه‌ی خام و اصلی یک محتوا (بند 19 و 20)."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin


class Document(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    __tablename__ = "documents"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    author: Mapped[str | None] = mapped_column(String(255))
    revision: Mapped[int | None] = mapped_column(Integer)

    hash: Mapped[str | None] = mapped_column(String(128), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)

    license: Mapped[str | None] = mapped_column(String(255))
    terms: Mapped[str | None] = mapped_column(Text)
    doc_metadata: Mapped[str | None] = mapped_column(Text)  # JSON (stringified)

    source: Mapped["Source | None"] = relationship(lazy="selectin")  # noqa: F821
    articles: Mapped[list["Article"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
