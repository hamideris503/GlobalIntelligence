# F05 — یکپارچه‌سازی Source Bot با ingestion مرکزی و ذخیرهٔ خام

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29 · **دامنه:** `source_bot/` + `domains/news/`

## English summary

All six adapters (RSS, HTML, XML, CSV, REST JSON, scrapy policy) implement the shared
`BaseFetcher`/`RawItem` contract (`source_bot/adapters/__init__.py` re-exports them); there is no
parallel ingest pipeline. `run_source` in `source_bot/runner.py` performs exact identity (`exact_key`,
`url_hash`, `identity_hash`), per-source DB dedup on `(source_id, hash, content_hash)`, priority scoring
with provenance, and persists via `deliver` into the central `Document` table. Raw text/payload is kept
for dedup/provenance; `run_post_ingest_dedup` runs after ingest. Source Bot tests (160) plus phase5/6/7
(211) pass. Live end-to-end ingest against real sources was not run (network), but the contract and
offline e2e tests cover the path.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_source_bot_e2e/endpoint/extract/fulltext/identity/identity_url_fallback/integration/priority_columns/priority_dedup/redirect_robots/stage2/validation` | 160 passed |
| `test_source_bot_phase5/6/7` | در suite 211 passed |
| adapters → `BaseFetcher`/`RawItem` | یک قرارداد واحد |
| `Document` با `(source_id, hash, content_hash)` | per-source dedup (نه global) |
| `run_post_ingest_dedup` پس از ingest | فراخوانی می‌شود |
| raw snapshot/provenance | `priority_meta`, `priority_source/status`, `duplicate_status`, `canonical_url`, `final_url`, `external_id` |

## ۲) محدودیت صریح

Ingest زنده روی منابع واقعی (شبکه) در این مرحله اجرا نشد؛ همهٔ تست‌ها آفلاین‌اند. اگر مالک بخواهد،
`run_once` روی یک منبع آزمایشی با شبکه قابل اجراست.
