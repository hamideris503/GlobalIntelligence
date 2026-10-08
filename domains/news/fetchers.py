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

    def __init__(self, timeout: float = 20.0, user_agent: str | None = None) -> None:
        self._timeout = timeout
        self._user_agent = user_agent or "GlobalIntelligenceBot/0.1"

    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        if not url:
            return []
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            content = resp.content
        return self.parse(content, limit=limit)

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
