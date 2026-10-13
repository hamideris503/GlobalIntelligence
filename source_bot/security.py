"""Security validator — اعتبارسنجی URL و SSRF guard.

متن وب غیرقابل‌اعتماد است؛ هیچ‌چیز اجرا نمی‌شود. کلید/هدر حساس
هرگز در log/exception قرار نمی‌گیرد (فقط نوع خطا ثبت می‌شود).
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

from domains.news.source_verify import host_is_private

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
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return UrlCheck(False, "private_ip")
    except ValueError:
        pass  # hostname است؛ بررسی DNS در fetch_url انجام می‌شود
    return UrlCheck(True, "")


def assert_public_host(host: str) -> None:
    """پس از redirect هم باید صدا زده شود؛ خطا می‌دهد اگر خصوصی باشد."""
    if not host or host_is_private(host):
        raise ValueError(f"refusing non-public host: {host or '?'}")


def redact_headers(headers: dict) -> dict:
    redacted = {}
    for k, v in headers.items():
        lk = k.lower()
        if any(s in lk for s in ("api-key", "apikey", "token", "auth", "secret", "cookie")):
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted
