"""Forecast, ForecastOutcome و Recommendation (بند 40-41, 49-50)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Forecast(UUIDMixin, TimestampMixin, Base):
    """هر پیش‌بینی مهم — هرگز حذف نمی‌شود (Forecast Ledger، بند 40)."""

    __tablename__ = "forecasts"

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    horizon: Mapped[str | None] = mapped_column(String(32))  # very_short/short/medium/long

    target: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    probability: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    interval_low: Mapped[float | None] = mapped_column(Float)
    interval_high: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    model: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    data_version: Mapped[str | None] = mapped_column(String(64))

    evidence: Mapped[str | None] = mapped_column(Text)  # JSON
    assumptions: Mapped[str | None] = mapped_column(Text)

    # --- Phase 26: Forecast Ledger ---
    # سناریو (base/bull/bear/tail — جزئیات در Phase 30)
    scenario: Mapped[str | None] = mapped_column(String(32), index=True)
    # چرخه‌ی حیات: active/superseded/expired/resolved (هرگز حذف نمی‌شود)
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False, server_default="active"
    )

    outcome: Mapped[ForecastOutcome | None] = relationship(
        back_populates="forecast", uselist=False, cascade="all, delete-orphan"
    )


class ForecastOutcome(UUIDMixin, TimestampMixin, Base):
    """نتیجه‌ی واقعی متصل به Forecast (بند 41)."""

    __tablename__ = "forecast_outcomes"

    forecast_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actual_value: Mapped[float | None] = mapped_column(Float)
    actual_bool: Mapped[str | None] = mapped_column(String(8))  # "true"/"false"
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # امتیازهای ارزیابی (بند 42) — محاسبه deterministic
    brier_score: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    abs_error: Mapped[float | None] = mapped_column(Float)
    squared_error: Mapped[float | None] = mapped_column(Float)

    notes: Mapped[str | None] = mapped_column(Text)

    forecast: Mapped[Forecast] = relationship(back_populates="outcome")


class Recommendation(UUIDMixin, TimestampMixin, Base):
    """خروجی Decision Engine (بند 49-50)."""

    __tablename__ = "recommendations"

    asset: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    direction: Mapped[str | None] = mapped_column(String(32))
    horizon: Mapped[str | None] = mapped_column(String(32))
    decision: Mapped[str | None] = mapped_column(String(32), index=True)

    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    expected_return: Mapped[float | None] = mapped_column(Float)
    downside: Mapped[float | None] = mapped_column(Float)
    probability_up: Mapped[float | None] = mapped_column(Float)
    probability_down: Mapped[float | None] = mapped_column(Float)

    base_scenario: Mapped[str | None] = mapped_column(Text)
    bull_scenario: Mapped[str | None] = mapped_column(Text)
    bear_scenario: Mapped[str | None] = mapped_column(Text)
    tail_risk: Mapped[str | None] = mapped_column(Text)

    evidence_for: Mapped[str | None] = mapped_column(Text)
    evidence_against: Mapped[str | None] = mapped_column(Text)
    main_drivers: Mapped[str | None] = mapped_column(Text)
    main_risks: Mapped[str | None] = mapped_column(Text)
    invalidation: Mapped[str | None] = mapped_column(Text)

    model: Mapped[str | None] = mapped_column(String(128))
    data_version: Mapped[str | None] = mapped_column(String(64))
    rank: Mapped[int | None] = mapped_column(Integer)
