"""Article — نسخه‌ی پردازش‌شده و قابل تحلیل یک Document (بند 21).

توجه: فیلدهای entities/topics/claims به‌صورت JSON (stringified) نگهداری می‌شوند
تا از پیچیدگی زودهنگام جداول واسط جلوگیری شود؛ در فازهای بعدی در صورت نیاز
به جداول رابطه‌ای تبدیل می‌شوند (Knowledge Graph در Phase 15).
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin


class Article(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    __tablename__ = "articles"

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    source_name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2), index=True)  # Phase 10

    topics: Mapped[str | None] = mapped_column(Text)  # JSON list
    entities: Mapped[str | None] = mapped_column(Text)  # JSON list
    sentiment: Mapped[float | None] = mapped_column(Float)
    stance: Mapped[str | None] = mapped_column(String(64))

    importance: Mapped[int | None] = mapped_column(Integer)  # 1 (مهم) .. 10 (عادی)
    confidence: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float)

    duplicate_cluster: Mapped[str | None] = mapped_column(String(128), index=True)
    event_cluster: Mapped[str | None] = mapped_column(String(128), index=True)

    # --- Phase 10 fix: وضعیت و ردیابی طبقه‌بندی ---
    classification_status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, index=True
    )  # pending | done | failed
    classification_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    classification_error: Mapped[str | None] = mapped_column(Text)
    classification_meta: Mapped[str | None] = mapped_column(Text)  # JSON: provider/model/prompt_version/...

    document: Mapped[Document | None] = relationship(  # noqa: F821
        back_populates="articles"
    )
    event: Mapped[Event | None] = relationship(back_populates="articles")  # noqa: F821
