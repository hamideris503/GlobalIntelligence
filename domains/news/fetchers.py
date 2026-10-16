"""Fetchers — دریافت خام از منابع (بند 16, Phase 8; بهبود Phase 10 fix).

- `BaseFetcher`: قرارداد یکسان
- `RSSFetcher`: پارس RSS/Atom با feedparser (استاندارد و مقاوم)
- `MockFetcher`: داده‌ی نمونه برای حالت آفلاین/MOCK_MODE (بند 73)

هیچ Fetcher نباید مستقیماً DB را بنویسد؛ فقط `RawItem` برمی‌گرداند.
`raw_payload` نسخه‌ی اصلی و دست‌نخورده‌ی آیتم (XML/JSON) را نگه می‌دارد (بند 19).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RawItem:
    """یک آیتم خام دریافتی از منبع، پیش از normalize."""

    title: str | None
    url: str | None
    raw_text: str | None
    published_at: datetime | None = None
    author: str | None = None
    language: str | None = None
    raw_payload: str | None = None  # نسخه‌ی اصلی و دست‌نخورده (XML/JSON)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseFetcher(ABC):
    """قرارداد دریافت."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        raise NotImplementedError


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None


class RSSFetcher(BaseFetcher):
    """پارس RSS 2.0 / Atom با feedparser (استاندارد)."""

    name = "rss"
    max_bytes = 5_000_000

    def __init__(self, timeout: float = 20.0, user_agent: str | None = None) -> None:
        self._timeout = timeout
        self._user_agent = user_agent or "GlobalIntelligenceBot/0.1"

    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        import asyncio as _asyncio

        if not url:
            return []
        # SSRF guard (census §7): فید مدیریتی هم باید عمومی باشد
        from urllib.parse import urlparse as _up

        from domains.news.source_verify import host_is_private
        host = (_up(url).hostname or "").lower()
        if not host or host_is_private(host):
            raise ValueError(f"refusing non-public feed host: {host or '?'}")
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }
        last_exc: Exception | None = None
        for attempt in range(2):  # یک retry با backoff برای timeout/5xx
            try:
                async with httpx.AsyncClient(timeout=self._timeout,
                                             follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"server error {resp.status_code}",
                            request=resp.request, response=resp)
                    resp.raise_for_status()
                    final_host = (_up(str(resp.url)).hostname or "").lower()
                    if host_is_private(final_host):
                        raise ValueError(f"redirected to private host: {final_host}")
                    content = resp.content
                    if len(content) > self.max_bytes:
                        raise ValueError(f"feed too big: {len(content)} bytes")
                    return self.parse(content, limit=limit)
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == 0:
                    await _asyncio.sleep(2.0)
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def parse(self, content: bytes, *, limit: int) -> list[RawItem]:
        """پارس محتوای فید (قابل تست با XML نمونه)."""
        import feedparser

        feed = feedparser.parse(content)
        items: list[RawItem] = []
        for entry in feed.entries[:limit]:
            # لینک: ترجیحاً alternate (نه self)
            link = entry.get("link")
            if not link:
                for lnk in entry.get("links", []) or []:
                    if lnk.get("rel") in (None, "alternate") and lnk.get("href"):
                        link = lnk["href"]
                        break

            # متن: content:encoded ترجیح دارد، سپس summary/description
            body = None
            content_list = entry.get("content") or []
            if content_list:
                body = content_list[0].get("value")
            body = body or entry.get("summary") or entry.get("description")

            published = entry.get("published") or entry.get("updated")
            author = entry.get("author")
            guid = entry.get("id") or link

            items.append(
                RawItem(
                    title=entry.get("title"),
                    url=link,
                    raw_text=body,
                    published_at=_parse_date(published),
                    author=author,
                    raw_payload=json.dumps(dict(entry), ensure_ascii=False, default=str),
                    metadata={"guid": guid, "feed_title": feed.feed.get("title")},
                )
            )
        return items


@dataclass
class FeedCheck:
    ok: bool
    items: int = 0
    final_url: str | None = None
    content_type: str | None = None
    reason: str = ""  # ok | not_feed | empty_feed | unreadable_items | <fetch error_kind>


def validate_feed(url: str | None, *, timeout: float = 20.0) -> FeedCheck:
    """اعتبارسنجی فید RSS بدون ذخیره‌سازی (single GET، بدون retry اضافه).

    از همان گارد SSRF/redirect/size مسیر fetch استفاده می‌کند؛ هیچ رکوردی
    نمی‌سازد و هیچ تابع storage را صدا نمی‌زند. فید معتبر = دست‌کم یک آیتم
    با title و link خوانا.
    """
    from domains.news.source_verify import fetch_url

    res = fetch_url(url or "", timeout=timeout)
    if not res.ok or not res.body:
        return FeedCheck(False, 0, res.final_url, res.content_type,
                         res.error_kind or "fetch_failed")
    try:
        items = RSSFetcher(timeout=timeout).parse(res.body, limit=50)
    except Exception:  # noqa: BLE001
        return FeedCheck(False, 0, res.final_url, res.content_type, "not_feed")
    if not items:
        head = res.body.lstrip()[:300].lower()
        if head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head:
            return FeedCheck(False, 0, res.final_url, res.content_type, "empty_feed")
        return FeedCheck(False, 0, res.final_url, res.content_type, "not_feed")
    good = sum(1 for it in items
               if (it.title or "").strip() and (it.url or "").strip())
    if not good:
        return FeedCheck(False, 0, res.final_url, res.content_type, "unreadable_items")
    return FeedCheck(True, good, res.final_url, res.content_type, "ok")


class MockFetcher(BaseFetcher):
    """داده‌ی نمونه‌ی deterministic برای حالت آفلاین (بند 73)."""

    name = "mock"

    SAMPLE = [
        {
            "title": "Central bank holds interest rate steady",
            "url": "https://example.local/news/1",
            "raw_text": "The central bank decided to keep the benchmark interest rate unchanged.",
            "author": "Mock Newsroom",
        },
        {
            "title": "Oil prices rise on supply concerns",
            "url": "https://example.local/news/2",
            "raw_text": "Crude oil prices increased amid reports of reduced supply.",
            "author": "Mock Newsroom",
        },
        {
            "title": "Inflation eases slightly in latest data",
            "url": "https://example.local/news/3",
            "raw_text": "Headline inflation moderated last month according to statistics.",
            "author": "Mock Newsroom",
        },
    ]

    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        now = datetime.now(UTC)
        items = []
        for i, s in enumerate(self.SAMPLE[:limit]):
            items.append(
                RawItem(
                    title=s["title"],
                    url=f"{s['url']}?v={now.date().isoformat()}",
                    raw_text=s["raw_text"],
                    published_at=now,
                    author=s["author"],
                    language="en",
                    raw_payload=json.dumps(s, ensure_ascii=False),
                    metadata={"mock": True, "index": i, "source_url": url},
                )
            )
        return items
