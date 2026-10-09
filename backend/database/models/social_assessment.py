"""Social assessment — خروجی Social Intelligence (Phase 23).

یک رکورد تحلیلی برای هر قلمرو (موضوع یا کشور) در هر ماه: میانگین احساس،
سهم ناآرامی، ترکیب موضع — همه قطعی و بدون AI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class SocialAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "social_assessments"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope", "period", name="uq_social_assess"),
    )

    scope_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # topic|country
    scope: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM

    avg_sentiment: Mapped[float | None] = mapped_column(Float)  # میانگین [-1, 1]
    article_count: Mapped[int | None] = mapped_column(Integer)
    unrest_share: Mapped[float | None] = mapped_column(Float)  # سهم [0, 1]
    stance_mix: Mapped[str | None] = mapped_column(Text)  # JSON فراوانی مواضع

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
