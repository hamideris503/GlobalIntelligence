"""HTML adapter — Scrapy موتور دریافت، Trafilatura استخراج (بدون دانلود مجدد).

جریان اجباری: Scrapy صفحه را می‌گیرد -> همان HTML + URL نهایی به trafilatura
تحویل می‌شود -> خروجی به RawItem تبدیل می‌شود.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from domains.news.fetchers import (
    EXTRACTION_FAILED,
    FULL_TEXT,
    TEXT_STATUS,
    RawItem,
)
from domains.news.source_verify import BlockedTarget, GuardedTransport, safe_get
from source_bot.security import validate_url


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
                  "date": date, "categories": cats,
                  # همان مسیر استخراج صفحهٔ مقاله که fulltext.enrich استفاده می‌کند؛
                  # عنوان‌تنها (بدون متن) = استخراج بی‌متن.
                  "mock": False,
                  TEXT_STATUS: FULL_TEXT if text else EXTRACTION_FAILED},
    )


def get_spider_class(collected=None, overrides: dict | None = None):
    """کلاس Spider واقعی Scrapy — موتور اصلی خزیدن.

    collected لیست مشترک خروجی است (در crawl چندپروسسی، همان لیست
    ساخته‌شده در worker پاس داده می‌شود تا خواندن از attribute کلاس
    لازم نباشد).

    overrides روی custom_settings اعمال می‌شود؛ چون custom_settings کلاس
    تنظیمات CrawlerProcess را سایه می‌اندازد، سقف‌های مؤثر باید همین‌جا ست شوند.
    """
    from scrapy import Spider  # type: ignore[import]
    from scrapy.http import Response  # type: ignore[import]

    box = collected if collected is not None else []
    custom = {
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "DEPTH_LIMIT": 2,
        "CLOSESPIDER_PAGECOUNT": 20,
        "RETRY_TIMES": 2,
        "LOG_ENABLED": False,
    }
    custom.update(overrides or {})

    class BotSpider(Spider):  # type: ignore[misc]
        name = "source_bot_spider"
        custom_settings = custom

        def __init__(self, start_urls=None, allowed_domains=None, authorized_origins=None,
                     diag=None, *a, **kw) -> None:
            super().__init__(*a, **kw)
            self.start_urls = start_urls or []
            self.allowed_domains = allowed_domains or []
            # originهای اجازه‌یافته فقط برای تست‌های محلی آفلاین (پیش‌فرض خالی = سیاست کامل)
            self.authorized_origins = tuple(authorized_origins or ())
            # شمارنده‌های تشخیصی: صفحه‌ی واقعاً گرفته‌شده و درخواست‌های مسدودشده‌ی policy
            self.diag = diag if isinstance(diag, dict) else {}
            self.collected = box

        def parse(self, response: Response):  # noqa: ANN201, ANN001
            self.diag["responses"] = self.diag.get("responses", 0) + 1
            html = response.text
            item = extract_with_trafilatura(html, str(response.url))
            if item is not None:
                self.collected.append(item)
                yield {"url": str(response.url), "title": item.title}
            # دنبال‌کردن پیوندهای مجاز در همان دامنه (فقط http/https)
            for href in response.css("a::attr(href)").getall()[:30]:
                abs_url = urljoin(str(response.url), href)
                scheme = urlparse(abs_url).scheme
                if scheme not in ("http", "https"):
                    continue
                if urlparse(abs_url).hostname in (self.allowed_domains or []):
                    yield response.follow(abs_url, callback=self.parse)

    return BotSpider


class CrawlError(RuntimeError):
    """خطای crawl چندصفحه‌ای (runner به تک‌صفحه برمی‌گردد)."""


def _crawl_settings(timeout_s: float, overrides: dict) -> dict:
    """تنظیمات CrawlerProcess؛ دو لایه‌ی سیاست اتصال همیشه اینجا حاضرند.

    یک نقطه‌ی حقیقت و قابل بازبینی: middleware (لایه ۱، هر درخواست) و resolver
    (لایه ۲، همان IP اتصال). پروکسی محیطی خاموش است تا اتصال مستقیم به IP
    تأییدشده برود.
    """
    return {
        "ROBOTSTXT_OBEY": True, "LOG_ENABLED": False,
        "DOWNLOAD_TIMEOUT": timeout_s,
        # لایه ۱: سیاست اتصال روی همه‌ی درخواست‌ها (redirect/robots/لینک صفحه)
        "DOWNLOADER_MIDDLEWARES": {
            "source_bot.adapters.scrapy_policy.ConnectionPolicyMiddleware": 100,
            # پروکسی محیطی خاموش: اتصال مستقیم به IP تأییدشده، بدون واسطه‌ی ناشناس
            "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": None,
        },
        # لایه ۲: همان resolver همان IP اتصال است (پنجره‌ی DNS-rebinding بسته)
        "DNS_RESOLVER": "source_bot.adapters.scrapy_policy.PolicyResolver",
        **overrides,
    }


def _crawl_worker(start_urls, allowed_domains, authorized_origins, timeout_s, overrides,
                  conn) -> None:
    """اجرای Scrapy در child پروسس: reactor هر بار تازه است (قابل restart نیست)."""
    try:
        import pickle

        from scrapy.crawler import CrawlerProcess  # type: ignore[import]

        collected: list = []
        diag: dict = {}  # responses/blocked — برای تفکیک crawl سالم-خالی از crawl مسدود
        spider_cls = get_spider_class(collected, overrides)
        # seam تست آفلاین: middleware و resolver از همین یک آرگومان تغذیه می‌شوند
        # و runner هرگز آن را پاس نمی‌دهد ⇒ در production سیاست کامل اجرا می‌شود.
        from source_bot.adapters.scrapy_policy import assert_policy_settings, set_test_origin_hosts

        set_test_origin_hosts(authorized_origins)
        process = CrawlerProcess(settings=_crawl_settings(timeout_s, overrides))
        crawler = process.create_crawler(spider_cls)
        process.crawl(crawler, start_urls=start_urls,
                      allowed_domains=allowed_domains,
                      authorized_origins=list(authorized_origins or ()),
                      diag=diag)
        # تنظیمات مؤثر پس از همه‌ی لایه‌ها (spider/custom/process/env) سنجیده می‌شود
        assert_policy_settings(crawler.settings)
        process.start()
        safe = []
        for it in collected:
            try:
                pickle.dumps(it)
                safe.append(it)
            except Exception:  # noqa: BLE001
                continue
        if not safe and not diag.get("responses") and diag.get("blocked"):
            # هیچ صفحه‌ای واکشی نشد چون سیاست همه‌ی درخواست‌ها را رد کرد
            conn.send(("blocked", str(diag["blocked"])))
        else:
            conn.send(("ok", safe))
    except Exception as exc:  # noqa: BLE001
        try:
            conn.send(("error", f"{type(exc).__name__}:{str(exc)[:200]}"))
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


class HtmlAdapter:
    """حالت سبک (httpx + trafilatura) برای تست + حالت Scrapy برای crawl واقعی."""

    name = "html"

    def __init__(self, timeout: float = 20.0, max_bytes: int = 5_000_000,
                 max_redirects: int = 3) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects

    async def fetch_url(self, url: str, *,
                        allowed_hosts: Iterable[str] = ()) -> HtmlResult:
        """`allowed_hosts` روی **هر hop** (از جمله مقصد redirect) اعمال می‌شود."""
        check = validate_url(url)
        if not check.ok:
            return HtmlResult([], "http_error", f"refusing url: {check.reason}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False,
                                         transport=GuardedTransport(
                                             allowed_hosts=allowed_hosts)) as client:
                # هر hop (از جمله مقصد redirect) پیش از اتصال بررسی می‌شود
                resp = await safe_get(
                    client, url, headers={"User-Agent": "GlobalIntelligenceBot/0.1",
                                          "Accept": "text/html"},
                    max_redirects=self.max_redirects, allow_hosts=allowed_hosts)
                if resp.status_code in (401, 403):
                    return HtmlResult([], "auth_required", f"http_{resp.status_code}")
                resp.raise_for_status()
                if len(resp.content) > self.max_bytes:
                    return HtmlResult([], "http_error", "html too big")
                final = str(resp.url)
                html = resp.text
        except BlockedTarget as exc:
            return HtmlResult([], "http_error", f"blocked: {exc}")
        except httpx.TimeoutException:
            return HtmlResult([], "http_error", "timeout")
        except Exception as exc:  # noqa: BLE001
            return HtmlResult([], "http_error", f"fetch_error:{type(exc).__name__}")
        item = extract_with_trafilatura(html, final)
        return HtmlResult([item] if item else [], "ok" if item else "empty", "", 1)

    def crawl(self, *, start_urls: list[str], allowed_domains: list[str],
              max_pages: int = 20, depth: int = 2, concurrency: int = 4,
              delay: float = 1.0, retries: int = 2, max_bytes: int | None = None,
              redirect_max: int = 3, authorized_origins: tuple[str, ...] = ()) -> list[RawItem]:
        """Crawl واقعی با Scrapy در child پروسس جدا (reactor قابل restart نیست).

        همه‌ی سقف‌ها (عمق، تعداد صفحه، هم‌زمانی، نرخ، اندازه پاسخ، redirect)
        واقعاً به Scrapy اعمال می‌شوند؛ پیش‌فرض‌ها همان کنترل‌های قبلی است.

        `authorized_origins` فقط seam تست‌های محلی آفلاین است (سرور 127.0.0.1) و
        middleware و resolver هر دو از همین یک آرگومان تغذیه می‌شوند؛
        runner/تنظیمات/API هیچ‌وقت آن را ست نمی‌کنند، پس در production لایه‌های
        `connection_check` و `PolicyResolver` کامل اجرا می‌شوند.

        خطا/تایم‌اوت -> CrawlError (runner به fetch_url تک‌صفحه برمی‌گردد).
        crawl‌ی که همه‌ی درخواست‌هایش را policy رد کرده باشد هم CrawlError
        می‌شود تا runner آن را «موفقیت با صفر آیتم» ثبت نکند.
        """
        import multiprocessing as _mp

        overrides = {
            "DEPTH_LIMIT": depth,
            "CLOSESPIDER_PAGECOUNT": max_pages,
            "CONCURRENT_REQUESTS": concurrency,
            "DOWNLOAD_DELAY": delay,
            "RETRY_TIMES": retries,
            "DOWNLOAD_MAXSIZE": self.max_bytes if max_bytes is None else max_bytes,
            "REDIRECT_MAX_TIMES": redirect_max,
        }
        deadline = self.timeout + 120.0
        ctx = _mp.get_context("spawn")
        rx, tx = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_crawl_worker,
            args=(list(start_urls), list(allowed_domains), list(authorized_origins),
                  self.timeout, overrides, tx),
            daemon=True,
        )
        proc.start()
        tx.close()
        try:
            if rx.poll(deadline):
                status, payload = rx.recv()
            else:
                status, payload = "error", "crawl timed out"
        finally:
            rx.close()
        proc.join(timeout=10)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=10)
        if status == "blocked":
            # سیاست اتصال همه‌ی درخواست‌ها را رد کرد: صفر آیتم ≠ موفقیت خالی
            raise CrawlError(f"crawl blocked by connection policy ({payload} requests)")
        if status != "ok":
            raise CrawlError(payload)
        return list(payload)
