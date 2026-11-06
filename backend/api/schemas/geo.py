"""مدل‌های پاسخ GeoJSON رویدادها (مرحله ۳)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    type: Literal["Point"] = "Point"
    # GeoJSON: [longitude, latitude]
    coordinates: list[float] = Field(min_length=2, max_length=2)


class GeoProperties(BaseModel):
    id: str
    category: str
    type: str | None = None
    title: str | None = None
    timestamp: str | None = None
    source: list[str] = []
    confidence: float | None = None
    country: str | None = None
    location: str | None = None
    location_precision: str | None = None
    location_source: str | None = None
    location_confidence: float | None = None
    extra: dict[str, Any] = {}


class GeoFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoPoint
    properties: GeoProperties


class GeoMetadata(BaseModel):
    total: int
    returned: int
    limit: int
    truncated: bool
    without_location: int


class GeoCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoFeature]
    metadata: GeoMetadata
