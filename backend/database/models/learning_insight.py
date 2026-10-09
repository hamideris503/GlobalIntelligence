"""Learning insight — یافته‌ی یادگرفته‌شده از تاریخچه (Phase 51).

بینش‌ها قطعی و بازتولیدپذیرند (روند، فراوانی، چندک) — نه نظر مدل.
هر دوره بازنویسی می‌شوند (upsert) چون داده‌ی جدید می‌رسد.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class LearningInsight(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learning_insights"
    __table_args__ = (
        UniqueConstraint("kind", "subject", "period", name="uq_learning_insight"),
    )

    kind: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    value: Mapped[str | None] = mapped_column(Text)  # JSON یافته
    confidence: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String(64))

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
