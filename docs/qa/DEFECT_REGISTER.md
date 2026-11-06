# Defect Register — GlobalIntelligence v1.5 QA

**Updated:** 2026-11-04 · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`
Lifecycle: `OPEN → TRIAGED → REPRODUCED → FIX_IN_PROGRESS → FIXED → REGRESSION_VERIFIED → CLOSED`.

## Closed and regression-verified

| Defect ID | Sev | Title | Root cause | Fix | Regression test | Status |
|---|---|---|---|---|---|---|
| GI-BUG-0001 | S1 | ETag/Last-Modified never sent because the runner rebuilt `RestJsonAdapter` per fetch | conditional state lived only on the instance | process-scoped `_SHARED_ETAG`/`_SHARED_LAST_MOD` consulted by `_etag_for`/`_last_mod_for` | `tests/test_source_bot_adapters_phase4.py::test_rest_json_conditional_headers_survive_adapter_rebuild` (new) | REGRESSION_VERIFIED |
| GI-BUG-0002 | S1 | Two concurrent `POST /api/ingest/jobs` could both create an active `JobRun` | check-then-insert with no DB guarantee | partial unique index `uq_job_runs_active` + `IntegrityError` handling | `tests/test_ingest_jobs.py::test_job_runs_active_unique_index_blocks_second_active_row` (new) | REGRESSION_VERIFIED |
| GI-BUG-0003 | S2 | Adaptive routing statistics never applied at runtime | no consumer of `AdaptiveRouter.build_routes` | `backend/ai/adaptive_bootstrap.py` wired into the lifespan, flag default off | `tests/test_adaptive_bootstrap.py` | REGRESSION_VERIFIED |
| GI-BUG-0011 | **S1** | A user without a key could not log in or paste a key from the UI: the global auth banner made `Section` hide every panel, including the login and key fields | `Section` suppressed children on *any* global issue, with no exemption for the recovery panels | new `recovery` prop on `Section`; login, manual-key and backend-URL panels opted in | `apps/web/e2e/fullstack.spec.ts:106` — previously timed out at `fill("رمز")`, now passes | REGRESSION_VERIFIED |
| GI-BUG-0012 | **S1** | After saving a key the header showed «کلید ثبت‌شده» but the stale «کلید ثبت نشده» banner kept every panel hidden | `saveKey` never reset the global issue (only `clearKey`/`retry` did) | `saveKey` clears the global issue for a non-empty key | `apps/web/e2e/fullstack.spec.ts:117` — previously failed at the provider row, now passes | REGRESSION_VERIFIED |
| GI-BUG-0005 | S3 | 16 frontend lint warnings | helpers exported from component modules; one unnecessary `useMemo` dep | split `format.ts` / `theme-context.ts`, internal-only exports, dropped the dead dep | `npm run lint` → **7 warnings, 0 errors** | PARTIALLY_CLOSED (7 remain) |

Both UI defects were invisible to the unit suite and appeared on the **first** real E2E run; after the fixes the
full full-stack suite passes **15/15 (48.8s)**.

## Open / carried (honest status)

| Defect ID | Sev | Title | Status | Blocker |
|---|---|---|---|---|
| GI-BUG-0004 | S2 | Priority thresholds not empirically calibrated (F-24) | BLOCKED | needs the human-labelled gold set (F04) |
| GI-BUG-0005b | S3 | 7 remaining `react-refresh` warnings in `ui.tsx` | OPEN (accepted) | they come from shared hooks/contexts in a 970-line module; splitting it needs a wider refactor with no runtime benefit |
| GI-BUG-0006 | S2 | Rate limiting is in-process only (F-23) | OPEN (documented) | single-process deployment today |
| GI-BUG-0008 | S2 | Live provider verification (F03, groq 403) | BLOCKED_EXTERNAL | network/region/key |
| GI-BUG-0009 | S2 | SMTP alert delivery never sent live | BLOCKED_EXTERNAL | `SMTP_*` credentials |
| GI-BUG-0010 | S3 | `Source` `topics`/`entities` as Text instead of JSONB (F-20) | OPEN (deferred) | 134 call sites read the stringified contract; a JSONB move is a schema decision, not a safe silent change |
| GI-BUG-0013 | S2 | PG-backed E2E (`playwright.pg-fullstack.config.ts`) not executed | BLOCKED (env) | the config expects a specific local PG credential; the SQLite full-stack and PG unit lanes both pass |

## Rules applied
- No test was deleted, skipped, `xfail`ed or weakened. The two E2E failures were fixed in product code, not in the assertions.
- No production data, volume or archive was touched; auto-purge remains OFF.
