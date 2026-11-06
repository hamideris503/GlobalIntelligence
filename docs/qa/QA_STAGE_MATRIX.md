# QA Stage Matrix — F00…F16

**Updated:** 2026-11-04 · **HEAD:** `42b2278` · Evidence: `docs/qa/QA_BASELINE.md`
Status vocabulary: `VERIFIED` / `PARTIALLY_VERIFIED` / `NOT_VERIFIED` / `BLOCKED` / `FAILED` /
`MISSING` / `SPEC_GAP` / `NOT_APPLICABLE`.

| Stage | Code present | Tests present | Tests executed (2026-11-04) | External dependency | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|
| F00 Baseline | yes | yes | git/status audit | no | `docs/BASELINE_F00.md`, this file | VERIFIED | — |
| F01 Build | yes | yes | ruff, `tsc`, `vite build` | no | `docs/F01_BUILD_VERIFICATION.md` | VERIFIED | — |
| F02 PG / CI / hygiene | yes | yes | PG full suite 1573 passed; migration chain from empty DB exit 0 | local PG 16 | `docs/F02_PG_LANE.md`, `docs/qa/QA_BASELINE.md` | VERIFIED (local) | remote CI run unverified (Python 3.12) |
| F02.5 Test hygiene | yes | yes | suite runs without temp/symlink errors | no | `docs/F02.5_TEST_HYGIENE.md` | VERIFIED | — |
| F03 Provider verification | yes | yes | not executed | live provider key/network | `docs/F03_PROVIDER_VERIFICATION.md` | BLOCKED | groq 403 region/network |
| F03.0 Config control plane | yes | yes | `tests/test_configuration_control_plane.py` in suite | no | `docs/F03_CONTROL_PLANE.md` | VERIFIED | — |
| F03.1 Catalog/discovery | yes | yes | in suite | no | `backend/configuration/*` | VERIFIED | — |
| F03.UX | yes | e2e specs | **E2E 15/15 passed** (48.8s) | local servers only | `docs/qa/QA_BASELINE.md`, `fullstack.spec.ts` | VERIFIED | 7 cosmetic lint warnings |
| F04 Kev/Laya evaluation | yes | subset | not executed | human labels | `docs/F04_*_REPORT.md` | BLOCKED | gold set + adjudication |
| F05 Source bot ingestion | yes | yes | `test_source_bot_*` in both lanes | no | `docs/F05_SOURCE_BOT_INGEST.md` | VERIFIED | — |
| F06 Adapter security/SSRF | yes | yes | `tests/test_security.py` (204 assertions) | no | `docs/F06_SECURITY.md` | VERIFIED | — |
| F07 Dedup/clusters | yes | yes | `test_dedup*`, `test_news_identity_phase7` | no | `docs/F07_DEDUP.md` | VERIFIED | — |
| F08 Priority/relevance | yes | yes | `test_priority_*` in suite | calibration data | `docs/F08_PRIORITY.md` | PARTIALLY_VERIFIED | thresholds not empirically calibrated (F-24) |
| F09 Jobs/dispatch | yes | yes | `test_dispatch`, `test_ingest_jobs` | no | `docs/F09_JOBS_DISPATCH.md` | VERIFIED | — |
| F10 Pending/mock recovery | yes | yes | `test_screening_recovery`, `test_mock_*` | no | `docs/F10_PENDING_MOCK.md` | VERIFIED | — |
| F11 Analysis pipeline | yes | yes | `test_domain_*`, `test_claims/events/evidence` | no | `docs/F11_ANALYSIS_PIPELINE.md` | VERIFIED | — |
| F12 Alerts/UI/monitoring | yes | yes | `test_alerts`, `test_alert_delivery*` | SMTP creds | `docs/F12_UI_API_ALERTS.md` | PARTIALLY_VERIFIED | live SMTP send blocked; Telegram live previously verified |
| F12.1.1 Source/integration UI | yes | yes | `test_f12_1_1_cluster_api` | no | `docs/F12_1_1_DEDUP_CLUSTER_API.md` | VERIFIED | — |
| F13 Retention/archive | yes | yes | `test_archive_*` in both lanes | Telegram creds for live | `docs/F13_RETENTION_ARCHIVE.md` | PARTIALLY_VERIFIED | disk monitoring; multi-archive live restore |
| F14 | Debt/perf/docs | yes | yes | JobRun index, ETag, adaptive apply regression-tested; lint 16→7 | no | `docs/F14_*`, `docs/qa/DEFECT_REGISTER.md` | PARTIALLY_VERIFIED | Text→JSONB (134 call sites), multi-process rate limit, 7 `ui.tsx` warnings |
| F15 | Local acceptance | yes | yes | full-stack E2E 15/15 (login, provider lifecycle, mock labelling, no outbound, cleanup) | local servers | `docs/BACKUP.md`, `docs/qa/QA_BASELINE.md` | PARTIALLY_VERIFIED | PG-backed E2E + restart/soak pass |
| F16 Forecast evaluation | yes | yes | `test_forecast`, `test_outcome`, `test_evaluation` | real forecasts/outcomes | `docs/STAGE_STATUS.md` | BLOCKED | needs resolved outcomes over time |

## Defects tied to stages
See `docs/qa/DEFECT_REGISTER.md`: GI-BUG-0001/0002/0003/0011/0012 closed and regression-verified
(the two UI ones were found by the first real E2E run); GI-BUG-0004…0013 open/blocked with explicit reasons.
