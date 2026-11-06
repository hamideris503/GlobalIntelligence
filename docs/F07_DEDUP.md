# F07 — exact/near dedup و cluster

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

Dedup is stdlib-based (shingling + MinHash + LSH + Union-Find) in `domains/news/dedup.py`, with exact
identity in `domains/news/normalizer.py` (`identity_hash`, `url_hash`, `identity_body`). Documents are
saved raw before any processing; uniqueness is per-source `(source_id, hash, content_hash)` — never global
content_hash (preserves independence signal). Dedup detects clusters (`duplicate_cluster`) without hard
delete; `corroborated` requires ≥2 independent sources. Post-ingest dedup runs after ingest
(`run_post_ingest_dedup`). Tests: `test_dedup` + `test_dedup_on_ingest` + `test_news_identity_phase7`
+ `test_document_identity_payload` + `test_source_bot_identity*` + `test_source_bot_priority_dedup` pass (247
suite total includes dispatch/classification/etc.).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_dedup.py` + `test_dedup_on_ingest.py` + `test_news_identity_phase7.py` + `test_document_identity_payload.py` + `test_source_bot_identity.py` + `test_source_bot_identity_url_fallback.py` + `test_source_bot_priority_dedup.py` | پاس (در suite 247 passed, 1 skipped) |
| exact identity (url_hash + identity_hash) | پوشش داده شده |
| near-duplicate (MinHash/LSH/Union-Find) | پوشش داده شده |
| per-source uniqueness (نه global content_hash) | تأیید شد (کد) |
| cluster بدون hard delete | تأیید شد |
| corroborated ≥2 منبع مستقل | قرارداد کد |

## ۲) محدودیت صریح

- near-duplicate threshold tuning روی دادهٔ واقعی (F-24) هنوز انجام نشده.
- hard-delete هرگز انجام نمی‌شود (طبق قرارداد).
