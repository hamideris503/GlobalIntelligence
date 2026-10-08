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
from datetime import UTC, datetime, timedelta
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
    raw_payload: str | None = None


def normalize(item: RawItem, *, retrieved_at: datetime | None = None) -> NormalizedItem:
    """یک RawItem را به شکل استاندارد تبدیل می‌کند.

    Point-in-Time:
    - `retrieved_at` = زمان واقعی دریافت (اکنون).
    - `available_at` = همان retrieved_at؛ چون «چه زمانی ما می‌توانستیم بدانیم»
      لزوماً زمان انتشار نیست و برای محتوای backfill/آینده نباید ادعای دانستن
      در گذشته کنیم (جلوگیری از look-ahead).
    - اگر published_at در آینده باشد (بیش از ۵ دقیقه)، آیتم مشکوک علامت‌گذاری
      و available_at روی retrieved_at می‌ماند.
    """
    now = retrieved_at or datetime.now(UTC)
    title = clean_text(item.title)
    body = clean_text(item.raw_text)

    published_at = item.published_at
    metadata = dict(item.metadata)
    if published_at is not None and published_at > now + timedelta(minutes=5):
        metadata["suspicious_future_published_at"] = published_at.isoformat()

    available_at = now  # اصلاح look-ahead: فقط زمانی که واقعاً دریافت شده
    observed_at = now

    return NormalizedItem(
        title=title,
        url=item.url,
        raw_payload=item.raw_payload,
        raw_text=body,
        language=item.language or detect_language(f"{title or ''} {body or ''}"),
        author=item.author,
        published_at=published_at,
        retrieved_at=now,
        available_at=available_at,
        observed_at=observed_at,
        hash=url_hash(item.url),
        content_hash=content_hash(title, body),
        metadata=metadata,
    )
