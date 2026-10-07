"""Pydantic schemas for ingestion & documents."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source_id: str | None = None
    source_name: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class IngestResultRead(BaseModel):
    source_name: str
    fetched: int
    stored: int
    duplicates: int
    errors: list[str]


class DocumentRead(BaseModel):
    id: str
    source_id: str | None
    url: str | None
    title: str | None
    language: str | None
    author: str | None
    published_at: datetime | None
    retrieved_at: datetime | None
    content_hash: str | None
