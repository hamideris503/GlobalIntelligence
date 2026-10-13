"""Source URL verifier — بررسی مؤدبانه و صادقانه‌ی نشانی‌ها (census).

- redirect chain کامل ثبت می‌شود (مقصد نهایی = canonical کاندید).
- سقف حجم/زمان، retry محدود فقط برای timeout/5xx، backoff.
- SSRF guard: هاست خصوصی/حلقه‌ای/link-local/metadata مسدود.
- هیچ‌چیز حدس زده نمی‌شود؛ نتیجه فقط چیزی است که واقعاً دیده شد.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 (GlobalIntelligenceBot https://example.local)"
)
MAX_BYTES = 1_000_000
TIMEOUT = 20.0
MAX_RETRIES = 1


@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status_code: int | None = None
    ok: bool = False
    error_kind: str | None = None  # timeout|dns|blocked|http_4xx|http_5xx|ssrf|too_big|...
    redirect_chain: list[str] = field(default_factory=list)
    elapsed_ms: float | None = None
    size_bytes: int = 0
    content_type: str | None = None
    body: bytes | None = None  # حداکثر MAX_BYTES (برای RSS/robots)


def host_is_private(host: str) -> bool:
    if not host:
        return True
    low = host.lower()
    if low == "localhost" or low.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(low)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast)
    except ValueError:
        pass
    # metadata ابری همیشه مسدود
    if low in ("169.254.169.254", "metadata.google.internal"):
        return True
    try:
        infos = socket.getaddrinfo(low, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    ips = []
    for info in infos:
        try:
            ips.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not ips:
        return False
    return all(bool(ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast) for ip in ips)


def fetch_url(url: str, *, timeout: float = TIMEOUT,
              max_bytes: int = MAX_BYTES, allow_private: bool = False) -> FetchResult:
    """یک URL را می‌گیرد؛ redirectها دنبال و ثبت می‌شوند.

    allow_private فقط برای تست محلی است (پیش‌فرض بسته).
    """
    res = FetchResult(url=url)
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        res.error_kind = "invalid_url"
        return res
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        res.error_kind = "invalid_url"
        return res
    if not allow_private and host_is_private(parsed.hostname):
        res.error_kind = "ssrf_blocked"
        return res

    attempts = 0
    while True:
        attempts += 1
        try:
            started = time.perf_counter()
            with httpx.Client(timeout=timeout, follow_redirects=True,
                              headers={"User-Agent": BROWSER_UA,
                                       "Accept": "text/html,application/rss+xml,"
                                                 "application/atom+xml,application/json,*/*"}) as client:
                resp = client.get(url)
            res.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            chain = [str(h.url) for h in resp.history] + [str(resp.url)]
            res.redirect_chain = chain
            res.final_url = str(resp.url)
            res.status_code = resp.status_code
            res.content_type = resp.headers.get("content-type")
            body = resp.content
            res.size_bytes = len(body)
            if len(body) > max_bytes:
                res.error_kind = "too_big"
                return res
            res.body = body
            if 200 <= resp.status_code < 300 and len(body) > 0:
                res.ok = True
                return res
            if resp.status_code in (401, 403):
                res.error_kind = "blocked"
            elif resp.status_code == 404:
                res.error_kind = "http_404"
            elif 400 <= resp.status_code < 500:
                res.error_kind = "http_4xx"
            elif resp.status_code >= 500:
                res.error_kind = "http_5xx"
            else:
                res.error_kind = f"http_{resp.status_code}"
            if res.error_kind in ("http_5xx",) and attempts <= MAX_RETRIES:
                time.sleep(2.0 * attempts)
                continue
            return res
        except httpx.TimeoutException:
            res.error_kind = "timeout"
            if attempts <= MAX_RETRIES:
                time.sleep(2.0 * attempts)
                continue
            return res
        except httpx.ConnectError:
            res.error_kind = "dns_or_connect"
            return res
        except Exception as exc:  # noqa: BLE001
            res.error_kind = f"fetch_error:{type(exc).__name__}"
            return res


def check_rss(rss_url: str, *, timeout: float = TIMEOUT,
              allow_private: bool = False) -> FetchResult:
    """اعتبارسنجی RSS/Atom: ریشه‌ی xml + حداقل یک آیتم."""
    res = fetch_url(rss_url, timeout=timeout, allow_private=allow_private)
    if not res.ok or res.status_code != 200 or not res.body:
        return res
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(res.body.decode("utf-8", errors="replace"))
        tag = root.tag.lower()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        is_feed = tag.endswith("rss") or tag.endswith("feed") or tag.endswith("rdf")
        items = len(root.findall(".//item")) + len(root.findall(".//atom:entry", ns))
        if is_feed and items > 0:
            res.ok = True
            return res
        res.ok = False
        res.error_kind = "rss_invalid"
        return res
    except Exception:  # noqa: BLE001
        res.ok = False
        res.error_kind = "rss_invalid"
        return res
