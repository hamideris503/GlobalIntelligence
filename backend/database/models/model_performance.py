"""Model performance — رکورد عملکرد مدل‌ها (Phase 36).

عملکرد تجمیعی هر مدل در هر ماه از outcomeهای امتیازدار، برای رتبه‌بندی
و ردیابی تاریخی دقت مدل‌ها (ورودی Adaptive Router در Phase 37).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class ModelPerformance(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_performance"

    __table_args__ = (
        UniqueConstraint("model", "period", name="uq_model_perf"),
    )

    model: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM

    n_scored: Mapped[int | None] = mapped_column(Integer)
    mae: Mapped[float | None] = mapped_column(Float)
    rmse: Mapped[float | None] = mapped_column(Float)
    mean_brier: Mapped[float | None] = mapped_column(Float)
    mean_log_loss: Mapped[float | None] = mapped_column(Float)

    method: Mapped[str | None] = mapped_column(String(64))

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
