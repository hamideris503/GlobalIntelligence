"""Source URL verifier — بررسی مؤدبانه و صادقانه‌ی نشانی‌ها (census).

- redirect chain کامل ثبت می‌شود (مقصد نهایی = canonical کاندید).
- سقف حجم/زمان، retry محدود فقط برای timeout/5xx، backoff.
- SSRF guard: هاست خصوصی/حلقه‌ای/link-local/metadata مسدود.
- اتصال واقعی به IP تأییدشده **pin** می‌شود (HTTPX/httpcore)؛ نام در زمان
  اتصال دوباره resolve نمی‌شود.
- هیچ‌چیز حدس زده نمی‌شود؛ نتیجه فقط چیزی است که واقعاً دیده شد.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpcore
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
MAX_FETCH_REDIRECTS = 5  # سقف زنجیره‌ی redirect در fetch_url (بعد از آن: too_many_redirects)


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


def is_forbidden_ip(value: object) -> bool:
    """آدرس IP (یا رشته‌ی آن) ممنوع است؟ یک نقطه‌ی حقیقت برای همه‌ی مسیرها.

    خصوصی/حلقه‌ای/link-local/multicast/reserved/unspecified و همچنین
    IPv4-mapped IPv6 (`::ffff:10.0.0.5` ⇒ همان 10.0.0.5 سنجیده می‌شود).
    رشته‌ی نامعتبر IP نیست ⇒ False (تصمیم نام‌محور به فراخوان واگذار می‌شود).
    """
    try:
        ip = ipaddress.ip_address(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def host_is_private(host: str) -> bool:
    if not host:
        return True
    low = host.lower()
    if low == "localhost" or low.endswith((".localhost", ".local", ".internal")):
        return True
    if is_forbidden_ip(low.strip("[]")):
        return True
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
    return all(is_forbidden_ip(ip) for ip in ips)


def resolve_host_ips(host: str) -> list[str]:
    """همه‌ی IPهای resolveشده یک هاست؛ [] اگر DNS پاسخ نداد.

    مصرف‌کننده‌ها باید [] را «مسدود» بدانند (fail-closed)، نه «عمومی».
    """
    if not host:
        return []
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return []
    out = []
    for info in infos or []:
        try:
            out.append(str(ipaddress.ip_address(info[4][0])))
        except (ValueError, IndexError):
            continue
    return sorted(set(out))


class BlockedTarget(ValueError):
    """مقصد غیرمجاز — پیش از هر اتصالی رد می‌شود."""


def _allowed_ips(host: str, *, allow_private: bool = False) -> tuple[list[str], str]:
    """(IPهای تأییدشده‌ی اتصال، دلیل رد) — یک نقطه‌ی حقیقت برای همه‌ی مسیرها.

    - وجود **یک** IP ممنوع در پاسخ DNS کافی است که مقصد مسدود شود
      (host_is_private فقط وقتی همه‌ی IPها خصوصی باشند مسدود می‌کند).
    - DNS ناموفق/بدون‌پاسخ/غیرقابل‌تفسیر → مسدود (fail-closed): «نامعلوم» با
      «عمومی» یکی گرفته نمی‌شود و درخواست بدون کنترل اجرا نمی‌شود.
    - `allow_private=True` فقط seam تست محلی است (پیش‌فرض بسته).
    """
    host = (host or "").strip("[]").lower()
    if not host:
        return [], "invalid_url"
    if allow_private:
        ips = resolve_host_ips(host)
        return (ips, "") if ips else ([], "dns_unresolved")
    if host_is_private(host):
        return [], "private_host"
    ips = resolve_host_ips(host)
    if not ips:
        return [], "dns_unresolved"
    for raw in ips:
        try:
            ipaddress.ip_address(raw)
        except ValueError:
            return [], f"unparsable_ip:{raw}"  # پاسخ غیرقابل‌اعتماد ⇒ اتصال نه
        if host_is_private(raw):  # همان IP resolve‌شده، نه رشته‌ی هاست
            return [], f"private_ip:{raw}"
    return ips, ""


def pinned_ip(host: str, *, allow_private: bool = False) -> str:
    """تنها IP مجاز اتصال به این میزبان؛ سیاست همین‌جا و پیش از سوکت اجرا می‌شود.

    خروجی همان IPی است که لایه‌ی اتصال به سوکت می‌دهد (بدون resolve دوباره)،
    پس «مقصد تأییدشده» و «مقصد اتصال» یکی هستند. رد ⇒ `BlockedTarget`.
    """
    ips, reason = _allowed_ips(host, allow_private=allow_private)
    if reason:
        raise BlockedTarget(reason)
    # shortcut: فقط اولین IP مجاز (بدون failover بین چند A-record)؛ اگر اتصال
    # پایدار به مقاصد چندآدرسی لازم شد، اینجا به تلاش روی IPهای بعدی ارتقا بده.
    return ips[0]


def target_allowed(url: str) -> tuple[bool, str]:
    """سیاست SSRF مسیرهای HTTPX، پیش از اتصال و به‌ازای هر hop."""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return False, "invalid_url"
    if p.scheme not in ("http", "https") or not p.hostname:
        return False, "invalid_url"
    if p.username or p.password:
        return False, "userinfo_forbidden"
    _ips, reason = _allowed_ips(p.hostname)
    if reason:
        return False, reason
    return True, ""


REDIRECT_CODES = (301, 302, 303, 307, 308)


def host_allowed(host: str, allowed: Iterable[str]) -> bool:
    """host برابر یا زیردامنهٔ یکی از دامنه‌های مجاز؛ lookalike رد می‌شود.

    `allowed` تهی یعنی «بدون allowlist» و تصمیم به گارد IP واگذار می‌شود.
    """
    host = (host or "").strip().lower().strip(".")
    if not host:
        return False
    for raw in allowed:
        entry = (raw or "").strip().lower().strip(".")
        if entry and (host == entry or host.endswith("." + entry)):
            return True
    return False


def _request_policy(url: str, allowed_hosts: Iterable[str]) -> tuple[bool, str]:
    """سیاست یک hop: اول allowlist دامنه (اگر داده شده)، بعد گارد IP/SSRF.

    allowlist پیش از `target_allowed` اجرا می‌شود تا مقصد خارج از فهرست حتی
    resolve هم نشود؛ public بودن IP مجوز عبور از allowlist نیست.
    """
    allowed = tuple(h for h in allowed_hosts if h)
    if allowed:
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return False, "invalid_url"
        if not host_allowed(host, allowed):
            return False, "host_not_allowed"
    return target_allowed(url)


class _PinnedAsyncBackend(httpcore.AsyncNetworkBackend):
    """backend اتصال: فقط IP تأییدشده‌ی همین لحظه به سوکت می‌رود.

    `host` ورودی همان hostname اصلی URL است (httpcore آن را از origin می‌دهد)،
    پس TLS/SNI و هدر Host دست‌نخورده می‌مانند و سوکت به IP pin می‌شود.
    """

    def __init__(self, inner: httpcore.AsyncNetworkBackend, *,
                 allow_private: bool = False) -> None:
        self._inner = inner
        self._allow_private = allow_private

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None,
                          local_address: str | None = None,
                          socket_options=None) -> httpcore.AsyncNetworkStream:  # noqa: ANN001
        target = pinned_ip(host, allow_private=self._allow_private)
        return await self._inner.connect_tcp(
            target, port, timeout=timeout, local_address=local_address,
            socket_options=socket_options)

    async def connect_unix_socket(self, path: str, timeout: float | None = None,
                                  socket_options=None) -> httpcore.AsyncNetworkStream:  # noqa: ANN001
        return await self._inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _PinnedSyncBackend(httpcore.NetworkBackend):
    """نسخه‌ی sync همان backend (مسیر `fetch_url`)."""

    def __init__(self, inner: httpcore.NetworkBackend, *,
                 allow_private: bool = False) -> None:
        self._inner = inner
        self._allow_private = allow_private

    def connect_tcp(self, host: str, port: int, timeout: float | None = None,
                    local_address: str | None = None,
                    socket_options=None) -> httpcore.NetworkStream:  # noqa: ANN001
        target = pinned_ip(host, allow_private=self._allow_private)
        return self._inner.connect_tcp(
            target, port, timeout=timeout, local_address=local_address,
            socket_options=socket_options)

    def connect_unix_socket(self, path: str, timeout: float | None = None,
                            socket_options=None) -> httpcore.NetworkStream:  # noqa: ANN001
        return self._inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options)

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def _pin_pool(pool: object, backend_cls: type, *, allow_private: bool = False) -> None:
    """backend پول HTTPX را با نسخه‌ی pin‌شده عوض می‌کند.

    shortcut: `_network_backend` تنها جای تزریق در پولی است که خود HTTPX ساخته
    (پارامتر عمومی `network_backend` فقط هنگام ساخت پول در دسترس است). اگر
    httpcore این نام را عوض کند، اجرا **متوقف** می‌شود؛ هرگز بی‌صدا به اتصال
    بدون pin برنمی‌گردد.
    """
    inner = getattr(pool, "_network_backend", None)
    if inner is None:
        raise RuntimeError("httpcore pool layout changed: cannot pin connections")
    pool._network_backend = backend_cls(inner, allow_private=allow_private)


class GuardedTransport(httpx.AsyncHTTPTransport):
    """سیاست `target_allowed` روی هر درخواست + pin اتصال به IP تأییدشده.

    `safe_get` هر hop را پیش از اتصال می‌سنجد؛ این transport همان سنجش را در
    نقطه‌ی ارسال تکرار می‌کند و اتصال واقعی را به همان IP تأییدشده pin می‌کند،
    پس نه رفتار redirect خود HTTPX و نه یک resolve دوباره نمی‌تواند مقصد را
    عوض کند. پروکسی/uds خطا هستند: مسیر مستقیم را دور می‌زنند.
    """

    def __init__(self, *args: object, allowed_hosts: Iterable[str] = (),
                 **kwargs: object) -> None:
        if args or kwargs.get("proxy") is not None or kwargs.get("uds") is not None:
            raise ValueError("proxy/uds/positional args unsupported: would bypass IP pinning")
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._allowed_hosts = tuple(h for h in allowed_hosts if h)
        _pin_pool(self._pool, _PinnedAsyncBackend)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        ok, reason = _request_policy(str(request.url), self._allowed_hosts)
        if not ok:
            raise BlockedTarget(reason)
        return await super().handle_async_request(request)


class GuardedSyncTransport(httpx.HTTPTransport):
    """برادر sync برای `fetch_url`: همان بررسی پیش از ارسال + pin اتصال.

    `allow_private` فقط seam تست محلی است (همان قرارداد `fetch_url`).
    """

    def __init__(self, *args: object, allow_private: bool = False,
                 allowed_hosts: Iterable[str] = (), **kwargs: object) -> None:
        if args or kwargs.get("proxy") is not None or kwargs.get("uds") is not None:
            raise ValueError("proxy/uds/positional args unsupported: would bypass IP pinning")
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._allow_private = allow_private
        self._allowed_hosts = tuple(h for h in allowed_hosts if h)
        _pin_pool(self._pool, _PinnedSyncBackend, allow_private=allow_private)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if not self._allow_private:
            ok, reason = _request_policy(str(request.url), self._allowed_hosts)
            if not ok:
                raise BlockedTarget(reason)
        return super().handle_request(request)


async def safe_get(client: httpx.AsyncClient, url: str, *,
                   headers: dict | None = None, max_redirects: int = 3,
                   allow_hosts: Iterable[str] = ()) -> httpx.Response:
    """GET با اعتبارسنجی هر hop **پیش از** اتصال؛ redirect خودکار دنبال نمی‌شود.

    علت: با `follow_redirects=True` اتصال به مقصد نهایی پیش از بررسی انجام
    می‌شود؛ پس کنترل ترتیب ندارد. اینجا هر hop قبل از درخواست بررسی می‌شود.

    `allow_hosts` (اختیاری) همان allowlist دامنه را روی **هر** hop اعمال می‌کند؛
    تهی = رفتار قبلی (فقط گارد IP).
    """
    for _ in range(max(1, max_redirects + 1)):
        ok, reason = _request_policy(url, allow_hosts)
        if not ok:
            raise BlockedTarget(reason)
        resp = await client.get(url, headers=headers)
        if resp.status_code in REDIRECT_CODES:
            loc = resp.headers.get("location")
            if not loc:
                raise BlockedTarget("redirect_without_location")
            url = urljoin(url, loc)
            continue
        return resp
    raise BlockedTarget("too_many_redirects")


def fetch_url(url: str, *, timeout: float = TIMEOUT,
              max_bytes: int = MAX_BYTES, allow_private: bool = False,
              allow_hosts: Iterable[str] = ()) -> FetchResult:
    """یک URL را می‌گیرد؛ زنجیره‌ی redirect **hop به hop** ثبت و بررسی می‌شود.

    redirect خودکار HTTPX خاموش است: هر مقصد پیش از اتصال با `target_allowed`
    سنجیده می‌شود، پس redirect به loopback/خصوصی/metadata هرگز اتصال نمی‌گیرد.
    علاوه بر آن، اتصال سوکت به همان IP تأییدشده pin است (نه resolve دوباره).
    قرارداد نتیجه (status/error_kind/redirect_chain/final_url/body) دست‌نخورده است.

    allow_private فقط برای تست محلی است (پیش‌فرض بسته) و در آن حالت سیاست
    per-hop هم (مثل قبل) اجرا نمی‌شود.
    """
    res = FetchResult(url=url)
    allowed = tuple(h for h in allow_hosts if h)
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

    current = url
    chain: list[str] = []
    attempts = 0
    while True:
        attempts += 1
        if not allow_private:
            allowed_hop, reason = _request_policy(current, allowed)
            if not allowed_hop:
                res.error_kind = ("host_not_allowed" if reason == "host_not_allowed"
                                  else "ssrf_blocked")
                res.final_url = current
                res.redirect_chain = chain
                logger.info("fetch blocked by policy | %s", reason)
                return res
        try:
            started = time.perf_counter()
            with httpx.Client(timeout=timeout, follow_redirects=False,
                              transport=GuardedSyncTransport(allow_private=allow_private,
                                                             allowed_hosts=allowed),
                              headers={"User-Agent": BROWSER_UA,
                                       "Accept": "text/html,application/rss+xml,"
                                                 "application/atom+xml,application/json,*/*"}) as client:
                resp = client.get(current)
            res.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            chain.append(str(resp.url))
            res.redirect_chain = chain
            res.final_url = str(resp.url)
            res.status_code = resp.status_code
            if resp.status_code in REDIRECT_CODES:
                loc = resp.headers.get("location")
                if not loc:
                    res.error_kind = "redirect_without_location"
                    return res
                if len(chain) > MAX_FETCH_REDIRECTS:
                    res.error_kind = "too_many_redirects"
                    return res
                current = urljoin(current, loc)
                continue
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
