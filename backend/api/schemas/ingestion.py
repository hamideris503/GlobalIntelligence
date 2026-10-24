"""Pydantic schemas for ingestion & documents."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# مجموعهٔ مجاز سطح اولویت (تنها منبع معنا: source_bot.priority_engine.LEVELS)
PriorityLevel = Literal["P0", "P1", "P2", "P3", "P4"]


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
    # Ingest priority (docs/SOURCE_BOT.md): persisted on the document, so the
    # read model must expose it — otherwise the P0..P4 decision is invisible.
    ingestion_priority: PriorityLevel | None = None
    priority_score: float | None = None
    priority_reason: str | None = None
    priority_source: str | None = None
    priority_status: str | None = None


class BotRunRequest(BaseModel):
    source_name: str | None = None
    limit: int = Field(default=20, ge=1, le=200)
    # سقف اختیاری آیتم پردازش‌شده از هر منبع؛ None = رفتار قبلی (بدون سقف)
    max_items_per_source: int | None = Field(default=None, ge=1, le=200)


class BotRunRead(BaseModel):
    sources_checked: int
    sources_ok: int
    sources_failed: dict[str, str]
    fetched: int
    stored: int
    duplicates: int
    items_skipped_limit: int = 0
    stopped: bool = False
    by_priority: dict[str, int]
    ai_used: int
    ai_fallback: int
    # تفکیک هر منبع در همین اجرا (کلید = نام منبع)؛ برای پایش یک‌بارهٔ کنترل‌شده.
    by_source: dict[str, dict] = {}


class IngestJobRead(BaseModel):
    """Job دریافت چندمنبعی — وضعیت، زمان‌ها و نتیجه‌ی ثبت‌شده در JobRun."""

    id: str
    job_name: str
    status: str
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    spec: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
