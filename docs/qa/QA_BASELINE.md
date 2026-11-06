# QA Baseline — GlobalIntelligence v1.5

**Date:** 2026-11-04 · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`
**Working tree:** owner's 184 modified/untracked paths preserved; no reset/stash/checkout was performed.

## 1) Executive status

`VERIFIED (local)` for backend, static and frontend gates. External capabilities remain
`BLOCKED_EXTERNAL_CREDENTIAL`. Two S1 UI defects were found by the E2E suite and fixed.

| Severity | Open | Closed (this execution) |
|---|---|---|
| S0 | 0 | 0 |
| S1 | 0 | 4 (ETag, job-run race, login unreachable, stale auth banner) |
| S2 | 4 (calibration, rate-limit scope, live provider, SMTP) | 1 (adaptive routing) |
| S3 | 2 (7 lint warnings, Text→JSONB) | 1 (lint 16→7) |

## 2) Tests executed (exact commands, real results)

| Test ID | Command | Environment | Result | Duration |
|---|---|---|---|---|
| QA-BASE-SQLITE | `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` | in-memory SQLite | **1570 passed, 1 skipped**, exit 0 | 293.27s |
| QA-BASE-PG | throwaway DB → `alembic upgrade head` → `pytest tests -q` → `DROP DATABASE` | PostgreSQL 16 (`127.0.0.1:15432`) | **1573 passed, 0 failed**; `ALEMBIC_UPGRADE_EXIT: 0` from an empty schema; DB dropped | 663.95s |
| QA-BASE-RUFF | `ruff check backend domains tests scripts source_bot` | host venv | `All checks passed!` | <5s |
| QA-BASE-HEADS | `alembic heads` | host venv | single head `b8c4d5e6f7a8` | <5s |
| QA-FE-LINT | `cd apps/web && npm run lint` | Node 24.16.0 | **0 errors, 7 warnings** (was 16) | ~20s |
| QA-FE-TSC | `npm run typecheck` | Node 24.16.0 | 0 errors, exit 0 | ~20s |
| QA-FE-BUILD | `npm run build` | Node 24.16.0 | success, JS 342.39 kB (gzip 109.09 kB) | 19.89s |
| QA-E2E-FULL | `npm run test:e2e:fullstack` | real FastAPI + SQLite + Vite, loopback only, outbound sockets blocked | **15 passed, 0 failed**, exit 0 | 48.8s |
| QA-REG-001 | `pytest tests/test_ingest_jobs.py::test_job_runs_active_unique_index_blocks_second_active_row` | SQLite | PASS | <1s |
| QA-REG-002 | `pytest "tests/test_source_bot_adapters_phase4.py::test_rest_json_conditional_headers_survive_adapter_rebuild"` | SQLite | PASS | <1s |

The E2E suite asserts more than rendering: no request leaves localhost
(`network-guard.log` empty), no unexpected browser error or ≥400 response, and the run removes every
row it created.

## 3) Defects found by the E2E run (both fixed)

1. **GI-BUG-0011** — with no API key the global auth banner made `Section` hide every panel, including
   the login form and the manual key field: the UI offered no way to recover. Fix: `Section` gained a
   `recovery` prop; the three recovery panels opt in. Proof: `fullstack.spec.ts:106` now passes
   (previously timed out waiting for the password field).
2. **GI-BUG-0012** — after saving a key the header showed «کلید ثبت‌شده» while the stale auth banner
   kept all panels hidden. Fix: `saveKey` clears the global issue. Proof: `fullstack.spec.ts:117`
   provider-creation test now passes.

## 4) Not run / blocked (explicit)

| Item | Status | Reason |
|---|---|---|
| PG-backed E2E (`test:e2e:pg`) | NOT RUN | config expects a specific local PG credential; not inferred or guessed |
| Live provider inference (F03) | BLOCKED_EXTERNAL | network/region 403 |
| SMTP live send | BLOCKED_EXTERNAL | no `SMTP_*` credentials |
| Kev/Laya full gold set | BLOCKED (human) | needs 100–200 labelled articles |
| Remote CI (Python 3.12) | NOT VERIFIED | local run is Python 3.14 |

## 5) Changes made in this execution

| File | Change | Reason |
|---|---|---|
| `tests/test_ingest_jobs.py` | DB-level single-active-job regression test | F-14 had no explicit guard |
| `tests/test_source_bot_adapters_phase4.py` | cross-instance conditional-header test + recording client | F-16 was documented as untested |
| `apps/web/src/ui.tsx` | `Section` `recovery` prop; `saveKey` clears the global issue | GI-BUG-0011 / GI-BUG-0012 |
| `apps/web/src/pages/settings.tsx` | login / key / backend-URL panels marked `recovery` | GI-BUG-0011 |
| `apps/web/src/format.ts`, `theme-context.ts`, `theme.tsx` | split helpers out of the theme module; 12 pages re-pointed | lint reduction without weakening rules |
| `apps/web/src/components/ui/{button,markdown,conversation}.tsx` | stop exporting symbols only used internally | lint reduction |
| `apps/web/src/pages/analysis.tsx` | removed a dead `useMemo` dependency | lint reduction |
| `docs/qa/*`, status docs | reconciled with measured results | docs must match reality |

No migration was added or edited; no backend behaviour changed in this step.

## 6) Security and data integrity
- No secret printed or logged; E2E asserts the key never appears in `localStorage` or page HTML.
- Outbound network is blocked at the socket layer during E2E, so "local only" is enforced, not assumed.
- Only disposable databases were used; auto-purge OFF; no archive or real DB touched.

## 7) Acceptance decision
`PASS (local)` for backend (both lanes), static checks, frontend build/typecheck/lint and the full-stack
E2E. Acceptance remains `CONDITIONAL` only for the external/human items in §4.

## 8) Next single stage
`QA-04` (configuration control plane) already has backend coverage; the highest-value remaining step is
running `test:e2e:pg` with a matching local PG credential to extend E2E evidence to PostgreSQL.
