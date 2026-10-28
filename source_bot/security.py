"""Security validator — اعتبارسنجی URL و SSRF guard.

متن وب غیرقابل‌اعتماد است؛ هیچ‌چیز اجرا نمی‌شود. کلید/هدر حساس
هرگز در log/exception قرار نمی‌گیرد (فقط نوع خطا ثبت می‌شود).
"""
from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from domains.news.source_verify import host_is_private, is_forbidden_ip, resolve_host_ips

ALLOWED_SCHEMES = ("http", "https")
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal")
CLOUD_METADATA = ("169.254.169.254", "metadata.google.internal", "fd00:ec2::254")


@dataclass
class UrlCheck:
    ok: bool
    reason: str = ""


def validate_url(url: str | None) -> UrlCheck:
    if not url or not isinstance(url, str):
        return UrlCheck(False, "empty_url")
    try:
        p = urlparse(url.strip())
    except Exception:  # noqa: BLE001
        return UrlCheck(False, "invalid_url")
    if p.scheme not in ALLOWED_SCHEMES:
        return UrlCheck(False, "bad_scheme")
    if p.username or p.password:
        return UrlCheck(False, "userinfo_forbidden")
    host = (p.hostname or "").lower()
    if not host:
        return UrlCheck(False, "no_host")
    if host in CLOUD_METADATA:
        return UrlCheck(False, "cloud_metadata_blocked")
    if host == "localhost" or host.endswith(BLOCKED_SUFFIXES):
        return UrlCheck(False, "private_host")
    try:
        ip = ipaddress.ip_address(host)
        if is_forbidden_ip(ip):
            return UrlCheck(False, "private_ip")
    except ValueError:
        pass  # hostname است؛ بررسی DNS در fetch_url انجام می‌شود
    return UrlCheck(True, "")


def assert_public_host(host: str) -> None:
    """پس از redirect هم باید صدا زده شود؛ خطا می‌دهد اگر خصوصی باشد."""
    if not host or host_is_private(host):
        raise ValueError(f"refusing non-public host: {host or '?'}")


def url_origin(url: str | None) -> str:
    """origin نرمال‌شده (scheme://host[:port]) برای مقایسه‌ی دقیق؛ "" اگر معتبر نباشد."""
    if not isinstance(url, str):
        return ""
    try:
        p = urlparse(url.strip())
        port = p.port  # پورت نامعتبر (مثل :bad) اینجا ValueError می‌دهد
    except Exception:  # noqa: BLE001
        return ""
    host = (p.hostname or "").lower()
    if not host:
        return ""
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"{p.scheme}://{host}:{port}" if port else f"{p.scheme}://{host}"


def connection_check(url: str | None, *, allow_origins: Iterable[str] = ()) -> UrlCheck:
    """سیاست اتصال برای **هر** درخواست واقعی (شامل redirect و لینک کشف‌شده).

    سخت‌گیرانه‌تر از `validate_url` است: علاوه بر scheme/userinfo/host،
    همه‌ی IPهای resolveشده باید عمومی باشند (DNS rebinding در سطح پاسخ DNS)،
    و DNS بدون پاسخ مسدود است (fail-closed).

    `allow_origins` فقط seam تست‌های محلی آفلاین است (origins دقیق مثل
    http://127.0.0.1:8080)؛ runner/تنظیمات/API هیچ‌وقت مقدار نمی‌دهند.
    """
    origin = url_origin(url)
    if origin and origin in set(allow_origins or ()):
        p = urlparse((url or "").strip())
        if (p.scheme in ALLOWED_SCHEMES and p.hostname
                and not (p.username or p.password)):
            return UrlCheck(True, "test_origin_allowed")
        return UrlCheck(False, "invalid_url")
    check = validate_url(url)
    if not check.ok:
        return check
    assert url
    host = (urlparse(url).hostname or "").lower()
    ips = resolve_host_ips(host)
    if not ips:
        return UrlCheck(False, "dns_unresolved")
    for raw in ips:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return UrlCheck(False, "unparsable_ip")
        if is_forbidden_ip(ip):
            return UrlCheck(False, f"private_ip:{ip}")
    return UrlCheck(True, "")


def vetted_ip(ip: str | None, name: str, *, allow_hosts: Iterable[str] = ()) -> str:
    """پاسخ resolver اسکرپی: **همان** IPی که تأیید شده به اتصال می‌رود.

    `ip` خروجی resolve است (همان چیزی که Twisted هنگام اتصال استفاده می‌کند)،
    پس بررسی و اتصال روی یک نتیجه انجام می‌شوند؛ یک resolve دوم وجود ندارد.
    ایمنی:
    - خود `ip` باید عمومی باشد (حتی اگر resolve دوم چیز دیگری بگوید).
    - هیچ IP ممنوعی در کل پاسخ DNS نباید باشد (وجود یکی کافی است).
    - DNS بی‌پاسخ/غیرقابل‌تفسیر → DNSLookupError (fail-closed، بدون اتصال).
    - `allow_hosts` فقط seam تست‌های آفلاین (loopback محلی) است؛ پیش‌فرض تهی.
    """
    from twisted.internet.error import DNSLookupError  # lazy: وابستگی فقط در خزیدن

    host = (name or "").lower().strip("[]")
    if host and host in set(allow_hosts or ()):
        if not ip:
            raise DNSLookupError(f"empty address for allowed test host {name}")
        return ip
    if not ip:
        raise DNSLookupError(f"no address resolved for {name}")
    if host_is_private(ip):
        raise DNSLookupError(f"blocked destination: non-public address for {name}")
    ips = resolve_host_ips(name)
    if not ips or any(host_is_private(raw) for raw in ips):
        raise DNSLookupError(f"blocked destination: unsafe dns answer for {name}")
    return ip


def redact_headers(headers: dict) -> dict:
    redacted = {}
    for k, v in headers.items():
        lk = k.lower()
        if any(s in lk for s in ("api-key", "apikey", "token", "auth", "secret", "cookie")):
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted
