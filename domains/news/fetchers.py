"""Fetchers — دریافت خام از منابع (بند 16, Phase 8).

- `BaseFetcher`: قرارداد یکسان
- `RSSFetcher`: پارس RSS/Atom با stdlib (بدون وابستگی اضافی)
- `MockFetcher`: داده‌ی نمونه برای حالت آفلاین/MOCK_MODE (بند 73)

هیچ Fetcher نباید مستقیماً DB را بنویسد؛ فقط `RawItem` برمی‌گرداند.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None


class RSSFetcher(BaseFetcher):
    """پارس فید RSS 2.0 و Atom با stdlib."""

    name = "rss"

    def __init__(self, timeout: float = 20.0, user_agent: str | None = None) -> None:
        self._timeout = timeout
        self._user_agent = user_agent or "GlobalIntelligenceBot/0.1"

    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        if not url:
            return []
        headers = {"User-Agent": self._user_agent}
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            content = resp.content
        return self._parse(content, limit=limit)

    def _parse(self, content: bytes, *, limit: int) -> list[RawItem]:
        root = ET.fromstring(content)
        items: list[RawItem] = []

        # RSS 2.0
        for item in root.iter("item"):
            items.append(self._item_rss(item))
            if len(items) >= limit:
                return items

        # Atom
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            items.append(self._entry_atom(entry, ns))
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _text(el: ET.Element | None) -> str | None:
        if el is None:
            return None
        return (el.text or "").strip() or None

    def _item_rss(self, item: ET.Element) -> RawItem:
        title = self._text(item.find("title"))
        link = self._text(item.find("link"))
        desc = self._text(item.find("description"))
        author = self._text(item.find("author")) or self._text(
            item.find("{http://purl.org/dc/elements/1.1/}creator")
        )
        pub = self._text(item.find("pubDate")) or self._text(
            item.find("{http://purl.org/dc/elements/1.1/}date")
        )
        guid = self._text(item.find("guid"))
        return RawItem(
            title=title,
            url=link or guid,
            raw_text=desc,
            published_at=_parse_date(pub),
            author=author,
            metadata={"guid": guid} if guid else {},
        )

    def _entry_atom(self, entry: ET.Element, ns: dict[str, str]) -> RawItem:
        title = self._text(entry.find("a:title", ns))
        link_el = entry.find("a:link", ns)
        link = link_el.get("href") if link_el is not None else None
        summary = self._text(entry.find("a:summary", ns)) or self._text(
            entry.find("a:content", ns)
        )
        author_el = entry.find("a:author/a:name", ns)
        author = self._text(author_el)
        pub = self._text(entry.find("a:published", ns)) or self._text(
            entry.find("a:updated", ns)
        )
        return RawItem(
            title=title,
            url=link,
            raw_text=summary,
            published_at=_parse_date(pub),
            author=author,
            metadata={},
        )


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
        now = datetime.now(timezone.utc)
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
                    metadata={"mock": True, "index": i, "source_url": url},
                )
            )
        return items
