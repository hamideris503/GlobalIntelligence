# WP-09 — Ingestion مرکزی و مدیریت منابع

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked؛ کانتینرها دست‌نخورده؛ هیچ Volume/DB حذف نشد.

## 2. Inventory ورودی‌ها

### 2.1 مسیرهای API (backend/api/routers/ingestion.py)

| Endpoint | کار | store |
|---|---|---|
| `POST /api/ingest` | یک منبع (source_id/name) | `NewsIngestionPipeline.ingest_source_async` |
| `POST /api/ingest/all` | همهٔ منابع فعال (rss+feed_url در حالت واقعی) | همان pipeline |
| `POST /api/ingest/bot` | Source Bot (تک‌منبع یا dueها) | `source_bot.runner.run_once` → همان pipeline |
| `POST /api/ingest/jobs` | Job چندمنبعی در پس‌زمینه | `source_bot.jobs` → همان pipeline |
| `GET /api/ingest/documents` | list Documents (بدون ingest) | فقط read |
| `GET /api/ingest/stats` | آمار قیف (fetched→stored) | فقط read |

### 2.2 Source Bot adapters (source_bot/adapters/)

| Adapter | فایل | preview (بدون ingest) |
|---|---|---|
| rss | `rss.py` | ✅ PREVIEW_ADAPTERS |
| rest_json | `rest_json.py` | — |
| csv | `csv.py` | — |
| xml | `xml.py` | — |
| html (Scrapy+Trafilatura) | `html.py` + `scrapy_policy.py` | — |
| specialized | `registry.py` (market/macro) | — |
| skip | — | — |

### 2.3 Economic/Market (جدا از News Article)

- `domains/markets/fetchers.py`: `ErApiFxFetcher`, `EcbFxFetcher`, `GoldApiFetcher`, `YahooFetcher`, `MockFetcher` (BaseFetcher مشترک).
- `domains/macro/fetchers.py`: `WorldBankFetcher`, `MockFetcher`.
- contract مشترک فقط در صورت نیاز فنی (BaseFetcher) — نه یکی‌سازی با Article.

### 2.4 Source Registry

- `domains/news/source_registry.py` (`SourceRegistry`) — تنها registry، بدون جدول موازی (ARCHITECTURE_TESTS.md تأیید).
- `source_bot/registry.py` — خواندن از `Source` موجود، بدون جدول موازی.

## 3. قرارداد Scrapy/Trafilatura (HTML)

- `source_bot/adapters/html.py`: Scrapy صفحه را می‌گیرد → همان HTML + URL نهایی به Trafilatura؛ **بدون دانلود دوم** (`test_single_http_download_then_trafilatura`, `test_crawl_extracts_from_the_same_response_with_trafilatura`).
- robots.txt: `ROBOTSTXT_OBEY` + `RobotFileParser` پیش از استخراج (مرحلهٔ ۲۵).
- SSRF: scheme/userinfo/loopback/private/metadata، pin IP، بررسی هر hop redirect، timeout/max_bytes/max_redirects، fail-closed.
- محدودیت مستند: Scrapy فقط IPv4 → AAAA-only fail-closed (F-27، `docs/F27_IPV6.md`).

## 4. جداسازی fetch/discovery/robots/retry/limits از extraction/persistence

- fetch/discovery/robots/retry/limits: `source_bot/adapters/scrapy_policy.py`, `html.py`, `fulltext.py`.
- extraction: Trafilatura روی HTML دریافت‌شده.
- persistence: `NewsIngestionPipeline` (store/dedup/priority) — یک pipeline واحد.
- `ARCHITECTURE_TESTS.md`: فقط یک `NewsIngestionPipeline`، یک `SourceRegistry`.

## 5. Raw payload/reference پایدار

- `Document.content_hash` (normalized)، `Document.url`، `published_at`, `retrieved_at`, `author`, `language`.
- metadata واقعی: source_id, external ID, original/canonical/final URL, title, text/raw ref, author, language, published/retrieved/processed time, hash, provenance, status.
- زمان انتشار (`published_at`)، دریافت (`retrieved_at`)، پردازش (created_at/processed) یکی نیستند (تست `test_normalize_point_in_time`).

## 6. Preview ≠ Ingestion

- `backend/configuration/preview.py` → `preview_fetch` (بدون store).
- `POST /api/sources/{id}/preview` → `ingested: false`، هیچ Document/Article اضافه نمی‌شود (`test_preview_never_ingests`).
- Source validation و preview از Ingestion واقعی جدا شده‌اند (config control plane).

## 7. Source failure isolation

- `test_broken_source_does_not_block_others`: یک منبع شکسته سایر منابع را متوقف نمی‌کند.
- `test_priority_failure_keeps_raw_document`: شکست priority سند خام را حفظ می‌کند.
- `test_unreliable_item_records_explicit_pending_status`: آیتم نامعتبر → status صریح pending (نه صامت).

## 8. Dedup و rerun

- `test_pipeline_deduplicates`: rerun → stored=0, duplicates=3 (بدون duplicate غیرمجاز).
- `test_same_item_from_two_sources_stored_twice`: همان آیتم از دو منبع → هر دو ذخیره (P0-3).
- `test_ingest_api_dedup_and_provenance_preserved`: provenance حفظ می‌شود.
- `test_no_double_store_across_ingest_paths`: بدون store دوباره در مسیرهای مختلف.

## 9. بررسی‌های اجراشده

- `pytest test_ingestion.py test_source_preview_api.py test_dedup_on_ingest.py test_source_bot_phase5/6/7.py test_source_bot_extract.py test_source_bot_fulltext.py` → **۱۶۶ passed** (۲۰۵.۴s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 10. وضعیت WP-09

| معیار پذیرش | نتیجه |
|---|---|
| Inventory تمام ورودی‌ها | PASS (§2) |
| Raw Item/Document/Registry/BaseFetcher/pipeline/normalizer/store/hookها خوانده شد | PASS |
| fetch/discovery/robots/retry/limits جدا از extraction/persistence | PASS (§4) |
| Scrapy fetch/discovery/robots/retry/domain; Trafilatura فقط روی HTML دانلودشده | PASS (§3) |
| Raw payload/reference پایدار | PASS (§5) |
| metadata واقعی + زمان‌های جدا | PASS (§5) |
| Preview ≠ Ingestion (بدون تغییر DB) | PASS (§6) |
| Source failure isolation | PASS (§7) |
| Economic/Market از Article جدا | PASS (§2.3) |
| یک Source واقعی از Registry تا persistence + lineage | PASS (test_pipeline_stores_documents) |
| rerun duplicate غیرمجاز نسازد | PASS (test_pipeline_deduplicates) |
| Preview هیچ ingest ناخواسته‌ای نکند | PASS (test_preview_never_ingests) |

**WP-09 در این نوبت کامل شد (inventory + contract verification). WP-10 شروع نشد.**