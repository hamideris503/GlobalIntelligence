"""Source Registry (بند 17)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin
from backend.database.enums import SourceType


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))  # ISO-3166 alpha-2
    type: Mapped[SourceType] = mapped_column(String(32), default=SourceType.other)
    language: Mapped[str | None] = mapped_column(String(16))

    credibility_score: Mapped[float | None] = mapped_column(Float)
    historical_accuracy: Mapped[float | None] = mapped_column(Float)
    correction_rate: Mapped[float | None] = mapped_column(Float)
    independence_score: Mapped[float | None] = mapped_column(Float)
    primary_source_ratio: Mapped[float | None] = mapped_column(Float)
    latency_seconds: Mapped[float | None] = mapped_column(Float)

    license: Mapped[str | None] = mapped_column(String(255))
    terms: Mapped[str | None] = mapped_column(Text)
    collection_method: Mapped[str | None] = mapped_column(String(64))

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
