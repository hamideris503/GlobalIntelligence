"""Briefing — گزارش دوره‌ای (روزانه/هفتگی) (Phase 41).

محتوا JSON است تا هفتگی (Phase 42) همین جدول را بازاستفاده کند.
هر دوره فقط یک رکورد (kind, period یکتا) — idempotent.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Briefing(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "briefings"
    __table_args__ = (
        UniqueConstraint("kind", "period", name="uq_briefing_kind_period"),
    )

    kind: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # daily|weekly
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM-DD
    title: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str | None] = mapped_column(Text)  # JSON بخش‌ها

    method: Mapped[str | None] = mapped_column(String(64))

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
