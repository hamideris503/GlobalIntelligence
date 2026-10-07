"""Scenario — Base/Bull/Bear/Tail با احتمال و شرط ابطال (بند 47-48)."""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Scenario(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"

    forecast_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # base|bull|bear|tail
    title: Mapped[str | None] = mapped_column(String(512))
    probability: Mapped[float | None] = mapped_column(Float)
    trigger: Mapped[str | None] = mapped_column(Text)
    expected_effect: Mapped[str | None] = mapped_column(Text)
    affected_assets: Mapped[str | None] = mapped_column(Text)  # JSON
    risks: Mapped[str | None] = mapped_column(Text)
    invalidation_criteria: Mapped[str | None] = mapped_column(Text)

    # تاریخچه‌ی تغییر احتمال (بند 48) به‌صورت JSON: [{ts, old, new, reason}]
    probability_history: Mapped[str | None] = mapped_column(Text)
