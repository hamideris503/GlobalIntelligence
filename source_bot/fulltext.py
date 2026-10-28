"""متن اصلی مقاله برای آیتم‌های RSS — یک GET به هر مقاله، همان HTML برای Trafilatura.

RSS معمولاً فقط خلاصه می‌دهد. اگر منبع، دامنهٔ مقاله را اعلام کرده باشد
(`endpoint_config.article_domains` یا env `SOURCE_BOT_ARTICLE_DOMAINS` یا
`homepage_url`/`canonical_url`/`domain`)، هر آیتمِ انتخاب‌شده یک‌بار از مسیر
محافظت‌شدهٔ `HtmlAdapter.fetch_url` گرفته می‌شود و متن همان HTML استخراج می‌شود.
پیش‌فرض (بدون دامنهٔ اعلام‌شده) = خاموش؛ هیچ fetch اضافه‌ای انجام نمی‌شود.

کنترل‌های مرحلهٔ ۲۵:
- allowlist دامنه روی **هر hop** redirect اعمال می‌شود (`safe_get`/transport).
- robots.txt پیش از دریافت مقاله از همان transport محافظت‌شده خوانده می‌شود؛
  ناموجود/نامعتبر/ممنوع ⇒ هیچ GET برای مقاله و حفظ خلاصهٔ RSS (fail-closed).
"""
from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from functools import partial
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from domains.news.fetchers import (
    EXTRACTION_FAILED,
    FULL_TEXT,
    RSS_SUMMARY_ONLY,
    TEXT_STATUS,
    RawItem,
)
from domains.news.normalizer import IDENTITY_TEXT_KEY
from domains.news.source_verify import GuardedTransport, host_allowed, safe_get
from source_bot.adapters.html import HtmlAdapter, HtmlResult
from source_bot.registry import endpoint_options
from source_bot.security import validate_url

TEXT_REASON = "text_reason"
SUMMARY_ONLY = RSS_SUMMARY_ONLY  # نام عمومی این ماژول حفظ می‌شود
REASON_HOST = "host_not_allowed"
REASON_ROBOTS_DISALLOWED = "robots_disallowed"
REASON_ROBOTS_UNAVAILABLE = "robots_unavailable"
REASON_EXTRACTION = "extraction_empty"
ENV_DOMAINS = "SOURCE_BOT_ARTICLE_DOMAINS"
ROBOTS_UA = "GlobalIntelligenceBot"
ROBOTS_MAX_BYTES = 512_000
_ROBOTS_UA_LINE = re.compile(r"(?im)^\s*user-agent\s*:")


def _no_extract_status(prior: object, current: str) -> str:
    """وضعیت متن وقتی استخراج مقاله نتیجه نداد.

    وضعیت صریح قبلی (مثلاً `source_provided_only` برای content:encoded) حفظ
    می‌شود؛ استخراج ناموفق نباید آن را به «خلاصه» تنزل دهد.
    """
    if isinstance(prior, str) and prior:
        return prior
    return SUMMARY_ONLY if current else EXTRACTION_FAILED



def _host(value: str | None) -> str:
    """host از یک URL یا host خالی از طرح/مسیر."""
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        try:
            return (urlparse(raw).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return ""
    return raw.split("/")[0].strip(".")


def _declared(value: object) -> list[str]:
    """دامنه‌های اعلام‌شده: رشتهٔ کاماجدا یا لیست."""
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(p) for p in value]
    else:
        return []
    return [h for h in (_host(p) for p in parts) if h]


def article_allowlist(source: object) -> tuple[str, ...]:
    """دامنه‌های مجاز برای صفحهٔ مقاله — فقط از دادهٔ منبع/فرایند، نه از URL فید."""
    hosts: list[str] = []
    cfg = endpoint_options(source) if source is not None else {}
    if isinstance(cfg, dict):
        hosts += _declared(cfg.get("article_domains"))
    hosts += _declared(os.getenv(ENV_DOMAINS, ""))
    if source is not None:
        hosts += _declared(getattr(source, "domain", None))
        hosts += _declared(getattr(source, "homepage_url", None))
        hosts += _declared(getattr(source, "canonical_url", None))
    return tuple(dict.fromkeys(hosts))


def _robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def _robots_parser(text: str | None, robots_url: str) -> RobotFileParser | None:
    """robots.txt نامعتبر ⇒ None (ممنوع).

    اعلان `user-agent` نداشتن یعنی پاسخ قابل‌اعتماد نیست (HTML خطا، متن خالی،
    بدنهٔ ناقص)؛ با robots استاندارد اشتباه گرفته نمی‌شود.
    """
    if not text or not _ROBOTS_UA_LINE.search(text):
        return None
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    return parser


async def _guarded_robots(robots_url: str, *, allowed_hosts: tuple[str, ...],
                          timeout: float, max_bytes: int,
                          max_redirects: int) -> str | None:
    """robots.txt از همان transport محافظت‌شده؛ هر خطا/وضعیت غیر‑200 ⇒ None.

    redirect خودکار خاموش است و allowlist روی هر hop اعمال می‌شود، پس robots
    نمی‌تواند به دامنهٔ خارج از فهرست بپرد. «نامعلوم» = «ممنوع» (fail-closed).
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                     transport=GuardedTransport(
                                         allowed_hosts=allowed_hosts)) as client:
            resp = await safe_get(client, robots_url, max_redirects=max_redirects,
                                  allow_hosts=allowed_hosts,
                                  headers={"User-Agent": ROBOTS_UA,
                                           "Accept": "text/plain"})
        if resp.status_code != 200 or len(resp.content) > min(max_bytes, ROBOTS_MAX_BYTES):
            return None
        return resp.text
    except Exception:  # noqa: BLE001 — robots ناخوانا هرگز به fetch مقاله تبدیل نمی‌شود
        return None


async def enrich_rss_items(
    items: list[RawItem], *,
    allowed_hosts: tuple[str, ...] | list[str],
    timeout: float = 20.0,
    max_bytes: int = 5_000_000,
    max_redirects: int = 3,
    delay: float = 1.0,
    fetch: Callable[[str], Awaitable[HtmlResult]] | None = None,
    robots_fetch: Callable[[str], Awaitable[str | None]] | None = None,
) -> None:
    """raw_text را با متن مقاله جایگزین می‌کند؛ شکستِ هر آیتم بقیه را خراب نمی‌کند.

    هر آیتم حداکثر یک GET دارد و خلاصهٔ RSS در `raw_payload` دست‌نخورده می‌ماند.
    robots.txt هر origin فقط یک‌بار در همین اجرا خوانده و کش می‌شود (بدون کش بین‌اجرایی).
    وضعیت در metadata: full_text_extracted | rss_summary_only | extraction_failed؛
    علت دقیق‌تر در `text_reason` (host_not_allowed | robots_disallowed |
    robots_unavailable | extraction_empty).

    `robots_fetch` فقط seam تست آفلاین است (URL robots ⇒ متن یا None).
    """
    allowed = tuple(h for h in allowed_hosts if h)
    if not allowed:
        return  # قابلیت خاموش: بدون درخواست و بدون تغییر
    adapter = HtmlAdapter(timeout=timeout, max_bytes=max_bytes,
                          max_redirects=max_redirects)
    do_fetch = fetch or partial(adapter.fetch_url, allowed_hosts=allowed)
    robots_for = robots_fetch or partial(_guarded_robots, allowed_hosts=allowed,
                                        timeout=timeout, max_bytes=max_bytes,
                                        max_redirects=max_redirects)
    robots_cache: dict[str, RobotFileParser | None] = {}
    first = True
    for item in items:
        meta = item.metadata if isinstance(item.metadata, dict) else {}
        item.metadata = meta
        meta.pop(TEXT_REASON, None)
        prior = meta.get(TEXT_STATUS)
        current = (item.raw_text or "").strip()
        url = item.url or ""
        if not host_allowed(_host(url), allowed) or not validate_url(url).ok:
            meta[TEXT_STATUS] = _no_extract_status(prior, current)
            meta[TEXT_REASON] = REASON_HOST
            continue
        robots_url = _robots_url(url)
        if robots_url not in robots_cache:
            try:
                robots_cache[robots_url] = _robots_parser(await robots_for(robots_url),
                                                          robots_url)
            except Exception:  # noqa: BLE001 — robots نامعلوم = ممنوع
                robots_cache[robots_url] = None
        robots = robots_cache[robots_url]
        if robots is None or not robots.can_fetch(ROBOTS_UA, url):
            meta[TEXT_STATUS] = _no_extract_status(prior, current)
            meta[TEXT_REASON] = (REASON_ROBOTS_UNAVAILABLE if robots is None
                                 else REASON_ROBOTS_DISALLOWED)
            continue
        if not first and delay > 0:
            await asyncio.sleep(delay)
        first = False
        text = ""
        try:
            result = await do_fetch(url)
            if result is not None and result.items:
                text = (result.items[0].raw_text or "").strip()
        except Exception:  # noqa: BLE001 — متن خراب یک مقاله نباید سند را از دست بدهد
            text = ""
        if text and len(text) > len(current):
            # هویت خبر روی متن اولیهٔ فید (خلاصه) می‌ماند؛ عوض‌کردن متن نباید
            # خبر را به رکورد/هویت مستقل تبدیل کند (رکورد تکراری/ریویژن کاذب).
            meta[IDENTITY_TEXT_KEY] = current
            item.raw_text = text
            meta[TEXT_STATUS] = FULL_TEXT
            meta["full_text_chars"] = len(text)
        else:
            meta[TEXT_STATUS] = _no_extract_status(prior, current)
            meta[TEXT_REASON] = REASON_EXTRACTION
