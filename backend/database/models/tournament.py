"""Tournament — رکورد یک تورنمنت مدل‌ها (Phase 29).

یک تورنمنت، اجرای چند روش روی اهداف مشترک و جدول امتیازات حاصل است.
نتایج (leaderboard) به‌صورت JSON ذخیره می‌شود تا تاریخچه‌ی رقابت‌ها بماند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Tournament(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tournaments"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    targets: Mapped[str | None] = mapped_column(Text)  # JSON لیست اهداف
    methods: Mapped[str | None] = mapped_column(Text)  # JSON لیست روش‌ها
    horizon: Mapped[str | None] = mapped_column(String(32))

    results: Mapped[str | None] = mapped_column(Text)  # JSON جدول امتیازات
    winner_model: Mapped[str | None] = mapped_column(String(128))
    n_forecasts: Mapped[int | None] = mapped_column(Integer)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
