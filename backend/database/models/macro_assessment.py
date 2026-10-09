"""Macro assessment — خروجی Macro Engine (Phase 21, بند MACRO ANALYSIS).

یک رکورد تحلیلی برای هر سری (indicator, country): آخرین مقدار، تغییر سالانه،
شتاب، z-score، momentum و برچسب آن — همه قطعی و بدون AI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class MacroAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "macro_assessments"
    __table_args__ = (
        UniqueConstraint("indicator", "country", "period", name="uq_macro_assess"),
    )

    indicator: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(3), index=True)
    period: Mapped[str | None] = mapped_column(String(32))

    latest_value: Mapped[float | None] = mapped_column(Float)
    yoy_change: Mapped[float | None] = mapped_column(Float)
    acceleration: Mapped[float | None] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)
    momentum: Mapped[float | None] = mapped_column(Float)  # در [-1, 1]
    momentum_label: Mapped[str | None] = mapped_column(String(32))

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    inputs: Mapped[str | None] = mapped_column(Text)  # JSON خلاصه‌ی ورودی‌ها

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
