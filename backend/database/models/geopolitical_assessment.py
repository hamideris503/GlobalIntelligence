"""Geopolitical assessment — خروجی Geopolitical Engine (Phase 22).

یک رکورد تحلیلی برای هر بازیگر در هر ماه: امتیاز تنش، سهم مناقشه،
تعداد رویدادها و انواع غالب — همه قطعی و بدون AI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class GeopoliticalAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "geopolitical_assessments"
    __table_args__ = (
        UniqueConstraint("actor", "period", name="uq_geo_assess"),
    )

    actor: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM

    tension: Mapped[float | None] = mapped_column(Float)  # در [0, 1]
    conflict_share: Mapped[float | None] = mapped_column(Float)
    event_count: Mapped[int | None] = mapped_column(Integer)
    sanction_links: Mapped[int | None] = mapped_column(Integer)
    top_types: Mapped[str | None] = mapped_column(Text)  # JSON فراوانی انواع

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
