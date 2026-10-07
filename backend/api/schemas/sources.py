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


class SourceRead(SourceBase):
    id: str
    last_success: datetime | None = None
    last_error: str | None = None


class SourceHealthUpdate(BaseModel):
    ok: bool
    error: str | None = None
