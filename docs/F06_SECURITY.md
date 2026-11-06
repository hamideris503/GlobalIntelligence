# F06 — امنیت adapterها و URLها

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

SSRF/redirect/DNS/IP-pinning is implemented in `domains/news/source_verify.py` and `source_bot/security.py`:
`is_forbidden_ip` covers IPv4 + IPv4-mapped IPv6, private/loopback/link-local/reserved/multicast/unspecified,
metadata hosts; `host_is_private` resolves DNS and fails closed on unresolved; `pinned_ip` pins the connection
to a verified IP (no second resolve); `GuardedTransport`/`GuardedSyncTransport` re-check policy per hop and
pin connections; `safe_get`/`fetch_url` follow redirects hop-by-hop with a cap (MAX_FETCH_REDIRECTS=5) and
per-hop SSRF checks; `validate_url`/`connection_check` block userinfo, bad schemes, metadata, private hosts.
Header redaction (`redact_headers`) strips secrets. Tests: 35 passed (`test_security`, `test_source_bot_redirect_robots`).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_security.py` + `test_source_bot_redirect_robots.py` | 35 passed |
| IPv4-mapped IPv6 | پوشش داده شده (`ipv4_mapped`) |
| redirect hop-by-hop + per-hop SSRF | پوشش داده شده |
| DNS fail-closed (unresolved → blocked) | پوشش داده شده |
| cloud metadata (169.254.169.254, metadata.google.internal) | مسدود |
| header redaction (api-key/token/auth/secret/cookie) | پوشش داده شده |

## ۲) محدودیت صریح

- IPv6-only/AAAA destinations (F-27) باید جداگانه با تست آزموده شوند؛ کد IPv4-mapped را پوشش می‌دهد اما
  تست صریح IPv6 در این مرحله اجرا نشد.
- live network SSRF test (opt-in) اجرا نشد.
