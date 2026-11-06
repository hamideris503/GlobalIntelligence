# Project Completion Status — GlobalIntelligence v1.5

**Last verified:** 2026-11-04 · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`

## Overall
- Backend (SQLite, in-memory): **1570 passed, 1 skipped** — 293.27s.
- Backend (PostgreSQL 16, database created, migrated from an empty schema, then dropped):
  **1573 passed, 0 failed** — 663.95s; `ALEMBIC_UPGRADE_EXIT: 0`, single head `b8c4d5e6f7a8`.
- Static: `ruff` → all checks passed.
- Frontend: lint **0 errors / 7 warnings** (down from 16), `tsc --noEmit` 0 errors, build success.
- **Full-stack E2E: 15 passed / 0 failed (48.8s)** against the real FastAPI app + SQLite + Vite,
  with outbound sockets blocked and a cleanup assertion.
- Auto-purge: **OFF**. No real database, volume or archive was touched.

## Closed this execution (regression-verified)
| ID | Defect | Proof |
|---|---|---|
| GI-BUG-0001 | ETag/Last-Modified lost when the runner rebuilt the adapter | `test_rest_json_conditional_headers_survive_adapter_rebuild` |
| GI-BUG-0002 | two concurrent requests could create two active ingest jobs | `test_job_runs_active_unique_index_blocks_second_active_row` |
| GI-BUG-0003 | adaptive routing statistics never applied at runtime | `tests/test_adaptive_bootstrap.py` |
| GI-BUG-0011 (S1) | without a key the UI hid its own login/key form behind the global banner | `fullstack.spec.ts:106` (previously timed out) |
| GI-BUG-0012 (S1) | after saving a key the stale banner kept every panel hidden | `fullstack.spec.ts:117` (previously failed) |

## Stage summary
See `docs/STAGE_STATUS.md`, `docs/ROADMAP_COMPLIANCE_MATRIX.md`, `docs/qa/QA_STAGE_MATRIX.md`.

## Acceptance (local)
- Backend both lanes: **PASS**. Frontend lint/typecheck/build: **PASS**. Full-stack E2E: **PASS**.
- Migration from empty schema on PG: **PASS**. Backup/restore: previously verified, not re-run today.
- PG-backed E2E and a restart/soak pass: **NOT RUN**.
- Live external integrations: **BLOCKED** (provider region/key, SMTP credentials, human gold set).

## Verdict
`PROJECT_COMPLETE_WITH_EXTERNAL_BLOCKERS`

The blocker list is unchanged and genuine: live provider verification (F03), the human-labelled gold set
(F04/F-24/F16), live SMTP delivery, and a second live Telegram archive round-trip. None can be closed
from the repository alone, and none is reported as verified.
