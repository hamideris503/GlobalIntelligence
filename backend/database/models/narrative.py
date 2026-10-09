"""Narrative — روایت غالب استخراج‌شده از خوشه‌ی رویدادها (Phase 24).

یک روایت، رشته‌ای از رویدادهای به‌هم‌پیوسته (موجودیت/موضوع مشترک) است
که گستردگی (منابع)، جهت‌گیری غالب و قدرت آن به‌صورت قطعی سنجیده می‌شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Narrative(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "narratives"
    __table_args__ = (
        UniqueConstraint("period", "signature", name="uq_narrative_sig"),
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # YYYY-MM
    signature: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    event_ids: Mapped[str | None] = mapped_column(Text)  # JSON لیست شناسه‌ها
    event_count: Mapped[int | None] = mapped_column(Integer)
    article_count: Mapped[int | None] = mapped_column(Integer)
    source_count: Mapped[int | None] = mapped_column(Integer)

    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dominant_stance: Mapped[str | None] = mapped_column(String(64))
    stance_divergence: Mapped[float | None] = mapped_column(Float)  # سهم غیرغالب [0, 1]
    strength: Mapped[float | None] = mapped_column(Float)  # قدرت [0, 1]

    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
