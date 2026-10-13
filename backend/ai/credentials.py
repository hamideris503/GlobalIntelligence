"""Provider credentials — رمزنگاری Fernet + ماسک + SSRF guard (Step 8).

قوانین:
- کلید هرگز لاگ/چاپ نمی‌شود؛ فقط key_set/key_hint به بیرون می‌رود.
- بدون APP_ENCRYPTION_KEY ذخیره رد می‌شود (نه متن ساده).
- base_url سفارشی: فقط https؛ هاست خصوصی/داخلی مسدود مگر فلگ صریح.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from backend.core.config import get_settings


class CredentialError(ValueError):
    """خطای امن اعتبارنامه (بدون مقدار حساس در متن)."""


def _fernet():
    from cryptography.fernet import Fernet, InvalidToken

    key = (get_settings().app_encryption_key or "").strip()
    if not key:
        raise CredentialError(
            "APP_ENCRYPTION_KEY is not set; refusing to store plaintext secrets. "
            "Generate one and put it in .env (see .env.example)."
        )
    try:
        return Fernet(key.encode("utf-8")), InvalidToken
    except Exception as exc:  # noqa: BLE001
        raise CredentialError("APP_ENCRYPTION_KEY is invalid") from exc


def encrypt_secret(plaintext: str) -> str:
    """رمزنگاری یک مقدار محرمانه (خروجی امن برای DB)."""
    fernet, _ = _fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """رمزگشایی (فقط سمت سرور، هرگز به API برنگردد)."""
    fernet, invalid = _fernet()
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except invalid as exc:
        raise CredentialError("stored secret cannot be decrypted") from exc


def mask_secret(hint_ok: bool = False, last4: str = "") -> str:
    """نمای ماسک‌شده برای UI: ••••xxxx یا 'not set'."""
    if not hint_ok:
        return "not set"
    return f"••••{last4}" if last4 else "••••"


def last4_of(plaintext: str) -> str:
    return plaintext[-4:] if len(plaintext) >= 4 else ""


def validate_base_url(base_url: str) -> str:
    """اعتبارسنجی ضد-SSRF برای base_url سفارشی. خروجی: URL نرمال‌شده.

    - فقط scheme برابر https (خالی → خطا).
    - هاست‌های خصوصی/حلقه‌ای/لینک‌لوکال/رزروشده مسدود، مگر
      ALLOW_PRIVATE_BASE_URL=true (فلگ صریح).
    """
    parsed = urlparse((base_url or "").strip())
    if parsed.scheme != "https":
        raise CredentialError("base_url must use https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise CredentialError("base_url has no host")
    if _host_is_private(host) and not get_settings().allow_private_base_url:
        raise CredentialError("base_url points to a private/internal host (blocked)")
    return f"https://{host}" + (f":{parsed.port}" if parsed.port else "") + parsed.path.rstrip("/")


def _host_is_private(host: str) -> bool:
    if host in ("localhost",):
        return True
    if host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        # عدم تفکیک‌پذیری ≠ خصوصی؛ خطای اتصال بعداً رخ می‌دهد (نه اینجا)
        return False
    ips = []
    for info in infos:
        try:
            ips.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not ips:
        return False
    return all(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        for ip in ips
    )
