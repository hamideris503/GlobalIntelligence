"""Provider run stats — عملکرد ثبت‌شده‌ی Providerها (Phase 37).

هر ردیف، تجمیع ماهانه‌ی یک (provider, model, task): تعداد فراخوانی،
موفقیت‌ها و مجموع تأخیر — ورودی مسیریابی تطبیقی.
"""
from __future__ import annotations

from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class ProviderRunStat(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "provider_run_stats"
    __table_args__ = (
        UniqueConstraint(
            "provider", "model", "task", "period", name="uq_provider_run"
        ),
    )

    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    task: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    structured_ok: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
