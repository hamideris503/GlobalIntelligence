"""Self-evaluation record — خودارزیابی دوره‌ای پلتفرم (Phase 39).

هر اجرا یک ردیف تاریخچه است (افزودنی) با نمره، grade و جزئیات چک‌ها.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class SelfEvaluation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "self_evaluations"

    score: Mapped[float | None] = mapped_column(Float)  # میانگین چک‌ها [0, 1]
    grade: Mapped[str | None] = mapped_column(String(8))  # A/B/C/D
    checks: Mapped[str | None] = mapped_column(Text)  # JSON لیست چک‌ها

    method: Mapped[str | None] = mapped_column(String(64))

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
