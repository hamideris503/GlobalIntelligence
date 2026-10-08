"""MarketObservation و MacroObservation — داده‌های سری زمانی (بند 16-17 Phases)."""
from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin


class MarketObservation(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    """یک مشاهده‌ی بازار (قیمت FX/طلا/نفت/سهام/...) در یک زمان."""

    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint("symbol", "observed_at", "source_name", name="uq_market_obs"),
    )

    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_class: Mapped[str | None] = mapped_column(String(64), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(8))
    source_name: Mapped[str | None] = mapped_column(String(255))
    raw: Mapped[str | None] = mapped_column(Text)


class MacroObservation(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    """یک مشاهده‌ی اقتصاد کلان (GDP/inflation/...) با ماهیت دوره‌ای."""

    __tablename__ = "macro_observations"
    __table_args__ = (
        UniqueConstraint(
            "indicator", "country", "period", "source_name", name="uq_macro_obs"
        ),
    )

    indicator: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(3), index=True)  # ISO-3
    period: Mapped[str | None] = mapped_column(String(32))  # e.g. 2026-Q1 / 2026-07
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    frequency: Mapped[str | None] = mapped_column(String(16))  # monthly/quarterly/annual
    source_name: Mapped[str | None] = mapped_column(String(255))
    revision: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[str | None] = mapped_column(Text)

    # --- Phase 16: Economic Data ---
    # شناسه‌ی سری زمانی منبع (مثلاً WB:FP.CPI.TOTL.ZG:USA) برای ردیابی
    series_id: Mapped[str | None] = mapped_column(String(255), index=True)
    # متادیتای اضافه (JSON) مثل واحد دقیق، توضیح منبع، لینک
    meta: Mapped[str | None] = mapped_column(Text)
