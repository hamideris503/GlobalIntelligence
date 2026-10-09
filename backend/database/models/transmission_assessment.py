"""Transmission assessment — خروجی Iran Transmission (Phase 34).

یک رکورد برای هر کانال انتقال در هر ماه: ورودی، وزن exposure،
اثر منتقل‌شده — قطعی و بدون AI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class TransmissionAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "transmission_assessments"
    __table_args__ = (
        UniqueConstraint("channel", "period", name="uq_transmission_assess"),
    )

    channel: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM

    input_value: Mapped[float | None] = mapped_column(Float)
    exposure: Mapped[float | None] = mapped_column(Float)  # وزن [0, 1]
    impact: Mapped[float | None] = mapped_column(Float)  # در [0, 1]
    drivers: Mapped[str | None] = mapped_column(Text)  # JSON

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
