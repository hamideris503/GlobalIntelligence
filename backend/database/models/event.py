"""Event — یک اتفاق واحد که چند Article به آن متصل می‌شوند (بند 23)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, PointInTimeMixin, TimestampMixin, UUIDMixin


class Event(UUIDMixin, TimestampMixin, PointInTimeMixin, Base):
    __tablename__ = "events"

    event_type: Mapped[str | None] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[str | None] = mapped_column(String(255))

    actors: Mapped[str | None] = mapped_column(Text)  # JSON list
    action: Mapped[str | None] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(Text)
    actual: Mapped[str | None] = mapped_column(Text)
    surprise: Mapped[float | None] = mapped_column(Float)

    affected_assets: Mapped[str | None] = mapped_column(Text)  # JSON list
    affected_indicators: Mapped[str | None] = mapped_column(Text)  # JSON list
    sources: Mapped[str | None] = mapped_column(Text)  # JSON list of source ids

    confidence: Mapped[float | None] = mapped_column(Float)
    event_metadata: Mapped[str | None] = mapped_column(Text)  # JSON (stringified)
    claims_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    articles: Mapped[list[Article]] = relationship(back_populates="event")  # noqa: F821
    claims: Mapped[list[Claim]] = relationship(back_populates="event")  # noqa: F821
