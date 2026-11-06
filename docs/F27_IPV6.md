# F27 — IPv4/IPv6 support (F-27)

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

IPv6 is handled in the SSRF guard without bypassing it:
- `is_forbidden_ip` in `domains/news/source_verify.py` covers IPv4 + IPv4-mapped IPv6 (`::ffff:`),
  private/ULA/link-local/unspecified/multicast/reserved, with `ipv4_mapped` unwrapping.
- `host_is_private`, `resolve_host_ips`, `_allowed_ips`, `target_allowed` work on IPv6 literals/hosts.
- `validate_url`/`connection_check` in `source_bot/security.py` reject private IPv6.
- Scrapy's `PolicyResolver` remains IPv4-oriented: AAAA-only destinations fail-closed (DNSLookupError)
  rather than being silently bypassed. This is an explicit, safe limitation, not a bypass.
- Added `test_ipv6_forbidden_and_mapped` (pure, no network) to `test_source_verify.py`.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_source_verify.py` | 7 passed (شامل تست IPv6 جدید) |
| IPv4-mapped private (no bypass) | پوشش داده شده |
| public IPv6 (not forbidden) | پوشش داده شده |
| Scrapy AAAA fail-closed | مستند (محدودیت صریح) |

## ۲) محدودیت صریح

- Scrapy resolver IPv4-only است؛ destinations فقط-AAAA به‌صورت fail-closed رد می‌شوند (نه bypass).
- IPv6-only host end-to-end crawl آزموده نشد (نیاز به منبع زنده).
