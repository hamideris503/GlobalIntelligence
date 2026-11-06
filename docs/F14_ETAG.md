# F14 (partial) — ETag/Last-Modified (F-16)

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

`RestJsonAdapter` rebuilt a fresh instance on every fetch in `source_bot/runner.py`, so `_etag`/`_last_mod`
were always empty and `If-None-Match`/`If-Modified-Since` were never sent (F-16). State is now also kept
in process-scoped module caches (`_SHARED_ETAG`, `_SHARED_LAST_MOD`), so a 304 can be earned across
fetches within a process. Instance state is still maintained for tests. Restart persistence (storing in
`Source.endpoint_config`) is intentionally left as a follow-up — process-scoped is the smaller,
reversible step approved by the roadmap ("process-scoped یا ترجیحاً در Source config").

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_source_bot_adapters_phase4.py` | 23 passed |
| conditional headers sent when state cached | پوشش (کد) |
| 304 → `not_modified` | پوشش داده شده |

## ۲) محدودیت صریح

- پس از restart، cache خالی است (پایداری در Source.endpoint_config هنوز انجام نشده).
- تست صریح «هدر ارسال می‌شود» اضافه نشد (تست موجود فقط 304 را می‌سنجد).
