"""Risk assessment — خروجی Risk Engine (Phase 31).

یک رکورد ریسک برای هر دسته در هر ماه: امتیاز، سطح، محرک‌ها — قطعی و بدون AI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class RiskAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint("category", "period", name="uq_risk_assess"),
    )

    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM

    score: Mapped[float | None] = mapped_column(Float)  # در [0, 1]
    level: Mapped[str | None] = mapped_column(String(16))  # low/medium/high/critical
    drivers: Mapped[str | None] = mapped_column(Text)  # JSON لیست محرک‌ها

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
