"""HTML adapter — Scrapy موتور دریافت، Trafilatura استخراج (بدون دانلود مجدد).

جریان اجباری: Scrapy صفحه را می‌گیرد -> همان HTML + URL نهایی به trafilatura
تحویل می‌شود -> خروجی به RawItem تبدیل می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from domains.news.fetchers import RawItem
from source_bot.security import assert_public_host, validate_url


@dataclass
class HtmlResult:
    items: list[RawItem]
    status: str
    detail: str = ""
    pages_visited: int = 0


def _doc_get(doc: object, key: str) -> object:
    if doc is None:
        return None
    if isinstance(doc, dict):
        return doc.get(key)
    return getattr(doc, key, None)


def extract_with_trafilatura(html: str, url: str) -> RawItem | None:
    """استخراج متن/metadata از همان HTML دریافتی؛ هیچ دانلود مجددی نیست."""
    try:
        from trafilatura import bare_extraction
    except Exception:  # noqa: BLE001
        return None
    try:
        doc = bare_extraction(html, include_comments=False, url=url)
    except Exception:  # noqa: BLE001
        return None
    if doc is None:
        return None
    text = (str(_doc_get(doc, "text") or "").strip()) or None
    title = (str(_doc_get(doc, "title") or "").strip()) or None
    if not text and not title:
        return None  # داده ساختگی نساز
    import json as _json

    author = _doc_get(doc, "author")
    sitename = _doc_get(doc, "sitename")
    date = _doc_get(doc, "date")
    cats = _doc_get(doc, "categories")

    return RawItem(
        title=title,
        url=url,
        raw_text=text,
        author=(str(author or "").strip()) or None,
        raw_payload=_json.dumps(
            {"title": title, "sitename": sitename,
             "categories": cats, "date": date},
            ensure_ascii=False, default=str,
        ),
        metadata={"adapter": "html", "sitename": sitename,
                  "date": date, "categories": cats},
    )


def get_spider_class():
    """کلاس Spider واقعی Scrapy — موتور اصلی خزیدن."""
    from scrapy import Spider  # type: ignore[import]
    from scrapy.http import Response  # type: ignore[import]

    collected: list = []

    class BotSpider(Spider):  # type: ignore[misc]
        name = "source_bot_spider"
        custom_settings = {
            "ROBOTSTXT_OBEY": True,
            "CONCURRENT_REQUESTS": 4,
            "DOWNLOAD_DELAY": 1.0,
            "DEPTH_LIMIT": 2,
            "CLOSESPIDER_PAGECOUNT": 20,
            "RETRY_TIMES": 2,
            "LOG_ENABLED": False,
        }

        def __init__(self, start_urls=None, allowed_domains=None, *a, **kw) -> None:
            super().__init__(*a, **kw)
            self.start_urls = start_urls or []
            self.allowed_domains = allowed_domains or []
            self.collected = collected

        def parse(self, response: Response):  # noqa: ANN201, ANN001
            html = response.text
            item = extract_with_trafilatura(html, str(response.url))
            if item is not None:
                self.collected.append(item)
                yield {"url": str(response.url), "title": item.title}
            # دنبال‌کردن پیوندهای مجاز در همان دامنه
            for href in response.css("a::attr(href)").getall()[:30]:
                abs_url = urljoin(str(response.url), href)
                if urlparse(abs_url).hostname in (self.allowed_domains or []):
                    yield response.follow(abs_url, callback=self.parse)

    return BotSpider


class HtmlAdapter:
    """حالت سبک (httpx + trafilatura) برای تست + حالت Scrapy برای crawl واقعی."""

    name = "html"

    def __init__(self, timeout: float = 20.0, max_bytes: int = 5_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    async def fetch_url(self, url: str) -> HtmlResult:
        check = validate_url(url)
        if not check.ok:
            return HtmlResult([], "http_error", f"refusing url: {check.reason}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "GlobalIntelligenceBot/0.1",
                                                      "Accept": "text/html"})
                if resp.status_code in (401, 403):
                    return HtmlResult([], "auth_required", f"http_{resp.status_code}")
                resp.raise_for_status()
                if len(resp.content) > self.max_bytes:
                    return HtmlResult([], "http_error", "html too big")
                final = str(resp.url)
                assert_public_host((urlparse(final).hostname or "").lower())
                html = resp.text
        except httpx.TimeoutException:
            return HtmlResult([], "http_error", "timeout")
        except Exception as exc:  # noqa: BLE001
            return HtmlResult([], "http_error", f"fetch_error:{type(exc).__name__}")
        item = extract_with_trafilatura(html, final)
        return HtmlResult([item] if item else [], "ok" if item else "empty", "", 1)

    def crawl(self, *, start_urls: list[str], allowed_domains: list[str]) -> list[RawItem]:
        """Crawl واقعی با Scrapy (blocking). دامنه‌ها محدود، robots رعایت می‌شود."""
        from scrapy.crawler import CrawlerProcess  # type: ignore[import]

        spider = get_spider_class()
        process = CrawlerProcess(settings={
            "ROBOTSTXT_OBEY": True, "CONCURRENT_REQUESTS": 4,
            "DOWNLOAD_DELAY": 1.0, "DEPTH_LIMIT": 2,
            "CLOSESPIDER_PAGECOUNT": 20, "RETRY_TIMES": 2, "LOG_ENABLED": False,
        })
        process.crawl(spider, start_urls=start_urls, allowed_domains=allowed_domains)
        process.start()
        return list(getattr(spider, "collected", []))
