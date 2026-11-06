# F19 — endpointهای سنگین (F-19)

**وضعیت:** NOT_STARTED (نیاز به اندازه‌گیری) · **تاریخ:** 2026-10-29

## English summary

F-19 requires measurement before moving anything. Candidate heavy endpoints (not yet profiled):
- `POST /api/ingest` and `/api/ingest/all` (run `NewsIngestionPipeline.ingest_source_async` in request thread).
- `POST /api/classify/run`, `/api/dedup/run`, `/api/events/extract`, `/api/claims/extract`.
- `/api/ai-routing/apply`, macro/risk/geopolitics/society `analyze_all`.

No endpoint was moved in this stage. The durable job path (`/api/ingest/jobs` + `run_job`) already exists
for ingest. Other endpoints should only be moved if a proven time/cost/timeout justifies it (F-19 rule).

## ۱) محدودیت صریح

- بدون اندازه‌گیری واقعی، انتقال به job پایدار ممنوع است.
- `workers/` همچنان placeholder است (jobs در-process اجرا می‌شوند) — طبق AGENTS.md.
- F-24 (thresholds) هم نیاز به دادهٔ واقعی دارد.


## Measurement update 2026-11-01

Profiled (PG, conftest engine, query count + latency):
- POST /api/ingest: 26 queries, 0.051s (3 articles) - acceptable
- POST /api/dedup/run: 6 queries, 0.024s - acceptable
- POST /api/classify/run: 106 queries, 0.183s (3 articles) - N+1 pattern but under 1s; no move justified
- GET /api/classify/articles: 2 queries, 0.019s - acceptable
- GET /api/events: 1 query, 0.011s - acceptable

Conclusion: No endpoint moved. classify/run shows N+1 but latency < 200ms for 3 articles; F-19 requires proven time/cost/timeout to justify move. No change applied.
