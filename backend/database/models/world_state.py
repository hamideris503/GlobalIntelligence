"""WorldState — تصویر ساختاریافته وضعیت جهان در یک لحظه (بند 33)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class WorldState(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "world_states"

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    granularity: Mapped[str | None] = mapped_column(String(16))  # hourly/daily/...

    growth_pressure: Mapped[float | None] = mapped_column(Float)
    inflation_pressure: Mapped[float | None] = mapped_column(Float)
    liquidity: Mapped[float | None] = mapped_column(Float)
    financial_stress: Mapped[float | None] = mapped_column(Float)
    geopolitical_risk: Mapped[float | None] = mapped_column(Float)
    energy_risk: Mapped[float | None] = mapped_column(Float)
    trade_risk: Mapped[float | None] = mapped_column(Float)
    political_risk: Mapped[float | None] = mapped_column(Float)
    social_pressure: Mapped[float | None] = mapped_column(Float)

    macro_regime: Mapped[str | None] = mapped_column(String(32))
    market_regime: Mapped[str | None] = mapped_column(String(32))

    # برای هر مقدار: source/method/confidence (بند 33) — JSON
    value_metadata: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
