"""RSS adapter — wrapper نازک روی RSSFetcher موجود (مسیر هم‌پوشان حذف نمی‌شود تا تست سبز شود)."""
from __future__ import annotations

from domains.news.fetchers import RawItem, RSSFetcher
from source_bot.security import validate_url


class BotRSSAdapter:
    name = "rss"

    def __init__(self, timeout: float = 20.0) -> None:
        self._inner = RSSFetcher(timeout=timeout)

    async def fetch(self, *, url: str | None, limit: int = 20) -> list[RawItem]:
        check = validate_url(url or "")
        if not check.ok:
            raise ValueError(f"refusing url: {check.reason}")
        return await self._inner.fetch(url=url, limit=limit)
