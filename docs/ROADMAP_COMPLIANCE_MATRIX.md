# Roadmap Compliance Matrix — GlobalIntelligence v1.5

**Updated:** 2026-11-04 · **HEAD:** `42b2278` · Evidence: `docs/qa/QA_BASELINE.md`,
`docs/qa/QA_STAGE_MATRIX.md`, `docs/qa/DEFECT_REGISTER.md`.

Status vocabulary: VERIFIED_COMPLETE, IMPLEMENTED_UNVERIFIED, PARTIAL, MISSING, BROKEN, INSECURE,
DEGRADED, DUPLICATED, DEAD_CODE, BLOCKED.

| Requirement ID | Description | Current Status | Evidence | Missing Work | Risk | Final Status |
|---|---|---|---|---|---|---|
| F00 | Baseline & reconciliation | VERIFIED_COMPLETE | `docs/BASELINE_F00.md`; working tree audited and preserved | — | Low | VERIFIED_COMPLETE |
| F01 | Build & static verification | VERIFIED_COMPLETE | ruff 0; `tsc --noEmit` 0; `vite build` success (2026-11-04) | — | Low | VERIFIED_COMPLETE |
| F02 | PostgreSQL / migration / CI | VERIFIED_COMPLETE | full PG suite **1573 passed / 0 failed** on a DB migrated from empty schema; SQLite **1570 passed / 1 skipped** | remote CI run (Python 3.12) not observed | Low | VERIFIED_COMPLETE (local) |
| F02.5 | Test hygiene | VERIFIED_COMPLETE | `docs/F02.5_TEST_HYGIENE.md`; run-private temp root | — | Low | VERIFIED_COMPLETE |
| F03 | Provider verification | BLOCKED | `docs/F03_PROVIDER_VERIFICATION.md` (groq 403 region/network) | live provider credentials/region | Medium | BLOCKED_EXTERNAL |
| F03.0 | Configuration control plane | VERIFIED_COMPLETE | `docs/F03_CONTROL_PLANE.md`; migration `a7f3c9d1e2b4` | — | Low | VERIFIED_COMPLETE |
| F03.1 | Provider catalog & discovery | VERIFIED_COMPLETE | `backend/configuration/*`, `tests/test_configuration_control_plane.py` | — | Low | VERIFIED_COMPLETE |
| F03.UX | UI/UX redesign | VERIFIED_COMPLETE | `docs/F03_UX_*`; **E2E 15/15 passed** (48.8s) against the real app after fixing two S1 UI defects; lint 0 errors/7 warnings | 7 `react-refresh` warnings in `ui.tsx` (cosmetic, HMR only) | Low | VERIFIED_COMPLETE |
| F04 | Human evaluation (Kev/Laya) | BLOCKED | `docs/F04_GOLDEN_SET.md`, `docs/F04_COMPARISON.md` (40-sample subset only) | 100–200 human-labelled articles + adjudication | High | BLOCKED (human) |
| F05 | Source Bot ingestion | VERIFIED_COMPLETE | `docs/F05_SOURCE_BOT_INGEST.md`; adapter tests both lanes | — | Low | VERIFIED_COMPLETE |
| F06 | Adapter security / SSRF | VERIFIED_COMPLETE | `docs/F06_SECURITY.md`, `docs/F27_IPV6.md`; `tests/test_security.py` | — | Low | VERIFIED_COMPLETE |
| F07 | Dedup & clusters | VERIFIED_COMPLETE | `docs/F07_DEDUP.md`; `tests/test_dedup*.py` | — | Low | VERIFIED_COMPLETE |
| F08 | Priority & relevance | PARTIAL | `docs/F08_PRIORITY.md`; boundary/provenance tests pass | empirical threshold calibration (F-24) needs F04 gold set | Medium | PARTIALLY_VERIFIED |
| F09 | Durable jobs & dispatch | VERIFIED_COMPLETE | `docs/F09_JOBS_DISPATCH.md`; atomic claim + unique active-job index regression-tested | — | Low | VERIFIED_COMPLETE |
| F10 | Pending/mock recovery | VERIFIED_COMPLETE | `docs/F10_PENDING_MOCK.md` | — | Low | VERIFIED_COMPLETE |
| F11 | Analysis pipeline | VERIFIED_COMPLETE | `docs/F11_ANALYSIS_PIPELINE.md` | — | Low | VERIFIED_COMPLETE |
| F12 | Alerts / UI / monitoring | PARTIAL | `docs/F12_UI_API_ALERTS.md`; delivery implemented with retry/idempotency; Telegram live previously verified | live SMTP send (credentials) | Medium | PARTIAL (live SMTP blocked) |
| F12.1.1 | Source & integration mgmt UI | VERIFIED_COMPLETE | `docs/F12_1_1_DEDUP_CLUSTER_API.md` | — | Low | VERIFIED_COMPLETE |
| F13 | Retention / archive | PARTIAL | `docs/F13_RETENTION_ARCHIVE.md`; catalog/restore/security tests pass; one live Telegram round-trip previously verified | disk monitoring; live restore for a second archive | Medium | PARTIAL (live blocked) |
| F14 | Debt / performance / docs | PARTIAL | JobRun race, ETag persistence, adaptive apply, IPv6, rate limit, N+1, heavy endpoints verified; lint warnings 16→7 | Text→JSONB (F-20, 134 call sites); multi-process rate limit (F-23); 7 `ui.tsx` warnings | Medium | PARTIALLY_VERIFIED |
| F15 | Local acceptance | PARTIAL | both backend lanes green; full-stack E2E 15/15 including login, provider lifecycle, mock labelling and cleanup; backup/restore verified earlier | PG-backed E2E and a restart/soak pass | Medium | PARTIALLY_VERIFIED |
| F16 | Forecast evaluation | BLOCKED | engine + metrics tests pass (`tests/test_forecast.py`, `test_evaluation.py`) | resolved outcomes over time | Low | BLOCKED (data) |

## Closed in this execution
- **GI-BUG-0001** ETag/Last-Modified state survives adapter rebuild — new regression test
  `test_rest_json_conditional_headers_survive_adapter_rebuild`.
- **GI-BUG-0002** second active `JobRun` rejected by the DB — new regression test
  `test_job_runs_active_unique_index_blocks_second_active_row`.
- **GI-BUG-0003** adaptive routing applied at startup behind a default-off flag — covered by
  `tests/test_adaptive_bootstrap.py`.
- **GI-BUG-0011 (S1)** an unauthenticated user could not reach the login/key form: the global auth
  banner made `Section` hide every panel. Fixed with a `recovery` opt-in; proof `fullstack.spec.ts:106`.
- **GI-BUG-0012 (S1)** the stale auth banner survived a successful key save, hiding all data while the
  header said «کلید ثبت‌شده». Fixed in `saveKey`; proof `fullstack.spec.ts:117`.

## Verification snapshot (2026-11-04)
```
ruff check backend domains tests scripts source_bot   -> All checks passed!
pytest tests -q (SQLite)                              -> 1570 passed, 1 skipped   (293.27s)
pytest tests -q (PostgreSQL, fresh migrated DB)       -> 1573 passed              (663.95s)
alembic upgrade head on empty DB                      -> exit 0, single head b8c4d5e6f7a8
npm run lint / typecheck / build                      -> 0 errors/7 warnings, 0 errors, success
npm run test:e2e:fullstack                            -> 15 passed (48.8s)
```
