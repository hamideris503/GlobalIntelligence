"""Source Registry (بند 17)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin
from backend.database.enums import SourceType


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))  # ISO-3166 alpha-2
    type: Mapped[str] = mapped_column(String(32), default=SourceType.other.value)
    language: Mapped[str | None] = mapped_column(String(16))

    credibility_score: Mapped[float | None] = mapped_column(Float)
    historical_accuracy: Mapped[float | None] = mapped_column(Float)
    correction_rate: Mapped[float | None] = mapped_column(Float)
    independence_score: Mapped[float | None] = mapped_column(Float)
    primary_source_ratio: Mapped[float | None] = mapped_column(Float)
    latency_seconds: Mapped[float | None] = mapped_column(Float)

    license: Mapped[str | None] = mapped_column(String(255))
    terms: Mapped[str | None] = mapped_column(Text)
    collection_method: Mapped[str | None] = mapped_column(String(64))  # rss|api|scrape|dataset

    # --- Phase 10 fix: آدرس فید واقعی و پیکربندی اندپوینت ---
    feed_url: Mapped[str | None] = mapped_column(Text)
    endpoint_config: Mapped[str | None] = mapped_column(Text)  # JSON (stringified)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    # --- Sources census (final prompt): هر URL در فیلد خودش، بدون ادغام ---
    homepage_url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    geography: Mapped[str | None] = mapped_column(String(32))  # global|country|region
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64))
    primary_or_secondary: Mapped[str | None] = mapped_column(String(16))  # primary|secondary
    official_status: Mapped[str | None] = mapped_column(String(16))  # official|media|...
    reliability_rationale: Mapped[str | None] = mapped_column(Text)
    bias_notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int | None] = mapped_column(Integer)
    access_model: Mapped[str | None] = mapped_column(String(32))  # free|registration|paid|...
    registration_required: Mapped[bool | None] = mapped_column(Boolean)
    api_url: Mapped[str | None] = mapped_column(Text)
    api_documentation_url: Mapped[str | None] = mapped_column(Text)
    api_auth_type: Mapped[str | None] = mapped_column(String(32))  # none|key|oauth|...
    rss_url: Mapped[str | None] = mapped_column(Text)
    sitemap_url: Mapped[str | None] = mapped_column(Text)
    archive_url: Mapped[str | None] = mapped_column(Text)
    data_download_url: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    license_terms: Mapped[str | None] = mapped_column(Text)
    robots_status: Mapped[str | None] = mapped_column(String(32))
    validation_status: Mapped[str] = mapped_column(
        String(32), default="PENDING_VALIDATION", nullable=False,
        server_default="PENDING_VALIDATION",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
