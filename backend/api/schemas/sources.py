"""Pydantic schemas for the Sources registry API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = None
    country: str | None = Field(default=None, max_length=2)
    type: str = "other"
    language: str | None = None
    credibility_score: float | None = None
    historical_accuracy: float | None = None
    correction_rate: float | None = None
    independence_score: float | None = None
    primary_source_ratio: float | None = None
    latency_seconds: float | None = None
    license: str | None = None
    terms: str | None = None
    collection_method: str | None = None
    active: bool = True
    feed_url: str | None = None
    # --- census fields (each URL in its own field) ---
    homepage_url: str | None = None
    canonical_url: str | None = None
    geography: str | None = None
    category: str | None = None
    subcategory: str | None = None
    primary_or_secondary: str | None = None
    official_status: str | None = None
    reliability_rationale: str | None = None
    bias_notes: str | None = None
    priority: int | None = None
    access_model: str | None = None
    registration_required: bool | None = None
    api_url: str | None = None
    api_documentation_url: str | None = None
    api_auth_type: str | None = None
    rss_url: str | None = None
    sitemap_url: str | None = None
    archive_url: str | None = None
    data_download_url: str | None = None
    terms_url: str | None = None
    license_terms: str | None = None
    robots_status: str | None = None
    validation_status: str = "PENDING_VALIDATION"
    last_checked_at: datetime | None = None


VALIDATION_STATUSES = (
    "PENDING_VALIDATION", "VERIFIED", "ACTIVE", "LIMITED_ACCESS",
    "AUTH_REQUIRED", "PAID", "TEMPORARILY_UNAVAILABLE", "INVALID_URL",
    "NEEDS_REVIEW", "DISABLED",
)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    domain: str | None = None
    country: str | None = None
    type: str | None = None
    language: str | None = None
    credibility_score: float | None = None
    historical_accuracy: float | None = None
    correction_rate: float | None = None
    independence_score: float | None = None
    primary_source_ratio: float | None = None
    latency_seconds: float | None = None
    license: str | None = None
    terms: str | None = None
    collection_method: str | None = None
    active: bool | None = None
    feed_url: str | None = None
    homepage_url: str | None = None
    canonical_url: str | None = None
    geography: str | None = None
    category: str | None = None
    subcategory: str | None = None
    primary_or_secondary: str | None = None
    official_status: str | None = None
    reliability_rationale: str | None = None
    bias_notes: str | None = None
    priority: int | None = None
    access_model: str | None = None
    registration_required: bool | None = None
    api_url: str | None = None
    api_documentation_url: str | None = None
    api_auth_type: str | None = None
    rss_url: str | None = None
    sitemap_url: str | None = None
    archive_url: str | None = None
    data_download_url: str | None = None
    terms_url: str | None = None
    license_terms: str | None = None
    robots_status: str | None = None
    validation_status: str | None = None
    last_checked_at: datetime | None = None


class SourceRead(SourceBase):
    id: str
    last_success: datetime | None = None
    last_error: str | None = None


class SourceHealthUpdate(BaseModel):
    ok: bool
    error: str | None = None
