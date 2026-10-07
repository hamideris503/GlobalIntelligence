"""Normalization — یکسان‌سازی آیتم خام به شکل استاندارد (Phase 8).

مسئول:
- پاک‌سازی متن و title
- محاسبه‌ی hash و content_hash (برای dedup در Phase 9)
- تشخیص زبان (ساده و heuristic — در فاز بعدی می‌تواند دقیق‌تر شود)
- ثبت زمان‌های Point-in-Time: published_at / retrieved_at / available_at / observed_at
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape

from domains.news.fetchers import RawItem

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")


def clean_text(text: str | None) -> str | None:
    """حذف تگ‌های HTML و فشرده‌سازی فاصله‌ها."""
    if not text:
        return None
    plain = unescape(_TAG_RE.sub(" ", text))
    plain = _WS_RE.sub(" ", plain).strip()
    return plain or None


def detect_language(text: str | None) -> str | None:
    """تشخیص ساده‌ی زبان بر اساس دامنه‌ی یونیکد."""
    if not text:
        return None
    if _PERSIAN_RE.search(text):
        return "fa"
    return "en"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def url_hash(url: str | None) -> str | None:
    return sha256(url) if url else None


def content_hash(title: str | None, body: str | None) -> str | None:
    payload = f"{(title or '').strip()}|{(body or '').strip()}"
    return sha256(payload) if payload.strip("|") else None


@dataclass
class NormalizedItem:
    title: str | None
    url: str | None
    raw_text: str | None
    language: str | None
    author: str | None
    published_at: datetime | None
    retrieved_at: datetime
    available_at: datetime
    observed_at: datetime
    hash: str | None
    content_hash: str | None
    metadata: dict


def normalize(item: RawItem, *, retrieved_at: datetime | None = None) -> NormalizedItem:
    """یک RawItem را به شکل استاندارد تبدیل می‌کند."""
    now = retrieved_at or datetime.now(timezone.utc)
    title = clean_text(item.title)
    body = clean_text(item.raw_text)

    # Point-in-Time: آنچه در زمان دریافت در دسترس بوده
    available_at = item.published_at or now
    observed_at = now

    return NormalizedItem(
        title=title,
        url=item.url,
        raw_text=body,
        language=item.language or detect_language(f"{title or ''} {body or ''}"),
        author=item.author,
        published_at=item.published_at,
        retrieved_at=now,
        available_at=available_at,
        observed_at=observed_at,
        hash=url_hash(item.url),
        content_hash=content_hash(title, body),
        metadata=item.metadata,
    )
