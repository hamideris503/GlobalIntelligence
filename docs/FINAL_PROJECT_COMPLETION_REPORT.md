# Final Project Completion Report — GlobalIntelligence v1.5

**Report date:** 2026-11-04 · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`
**Scope:** local audit, verification and remediation. No deployment, no VPS, no production change.

## A. Executive Summary
- Every locally executable gate passes: backend full suite on **both** engines, static checks,
  frontend lint/typecheck/build, and a migration chain rebuilt from an empty PostgreSQL schema.
- Three previously fixed defects that lacked explicit regression coverage now have it, and both
  new tests pass.
- Remaining gaps are external or human: live provider access, SMTP credentials, and a human-labelled
  evaluation set. They are reported as blocked, never as verified.
- **Verdict: `PROJECT_COMPLETE_WITH_EXTERNAL_BLOCKERS`.**

## B. Roadmap Compliance
Full table: `docs/ROADMAP_COMPLIANCE_MATRIX.md`. Stage reconciliation:
`docs/qa/QA_STAGE_MATRIX.md`. Requirement→test traceability: `docs/qa/TRACEABILITY_MATRIX.csv`.

| Band | Stages | Status |
|---|---|---|
| Core verified | F00, F01, F02, F02.5, F03.0, F03.1, F05–F07, F09–F11, F12.1.1 | VERIFIED_COMPLETE |
| Partial | F03.UX, F08, F12, F13, F14, F15 | PARTIALLY_VERIFIED (each with a named gap) |
| Blocked | F03, F04, F16 | BLOCKED (external credential / human data) |

## C. Implementation Summary
No production code was rewritten this execution. The working tree already contained the fixes for
the open P1 items; they were verified and hardened with tests:
- `source_bot/adapters/rest_json.py` — process-scoped `_SHARED_ETAG` / `_SHARED_LAST_MOD`.
- `source_bot/jobs.py` + `db/migrations/versions/f14a0b1c2d3e_job_runs_active_unique.py` —
  partial unique index `uq_job_runs_active` and `IntegrityError` handling.
- `backend/ai/adaptive_bootstrap.py` + `backend/main.py` lifespan — adaptive route apply behind
  `ADAPTIVE_ROUTING_ENABLED` (default off).

## D. Bug Fixes
| ID | Sev | Root cause | Fix location | Proof |
|---|---|---|---|---|
| GI-BUG-0001 | S1 | conditional-header state lived only on the adapter instance | `source_bot/adapters/rest_json.py` | new cross-instance test passes; suite green |
| GI-BUG-0002 | S1 | check-then-insert with no DB guarantee | `source_bot/jobs.py`, migration `f14a0b1c2d3e` | new DB-level test passes on SQLite and PG |
| GI-BUG-0003 | S2 | no runtime consumer of `AdaptiveRouter.build_routes` | `backend/ai/adaptive_bootstrap.py`, `backend/main.py` | `tests/test_adaptive_bootstrap.py` |
| GI-BUG-0011 | S1 | `Section` hid every panel on a global auth issue, including the login/key form, so a user without a key could not recover | `apps/web/src/ui.tsx`, `apps/web/src/pages/settings.tsx` | full-stack E2E `fullstack.spec.ts:106` (previously timed out) |
| GI-BUG-0012 | S1 | `saveKey` never cleared the stale auth banner, so saved keys left all data hidden | `apps/web/src/ui.tsx` | full-stack E2E `fullstack.spec.ts:117` (previously failed) |

## E. Dead Code & Refactoring
None removed. No file was deleted on suspicion alone; `source_bot/normalizer.py` remains deleted as
the owner's pre-existing working-tree change (not touched by this execution).

## F. Test Results (exact)
```
.venv/Scripts/python.exe -m ruff check backend domains tests scripts source_bot
  -> All checks passed!

.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider
  -> 1570 passed, 1 skipped, 610 warnings in 293.27s

# PostgreSQL lane: throwaway DB gi_qa_8fa4abf1 created, migrated, used, dropped
alembic upgrade head   -> ALEMBIC_UPGRADE_EXIT: 0 (single head b8c4d5e6f7a8)
pytest tests -q        -> 1573 passed, 610 warnings in 663.95s
DROP DATABASE          -> test database dropped

cd apps/web
npm run lint       -> 0 errors, 7 warnings (exit 0)
npm run typecheck  -> exit 0
npm run build      -> 1958 modules; dist JS 342.33 kB (gzip 109.03 kB); built in 26.76s
```
```
cd apps/web && npm run test:e2e:fullstack
  -> 15 passed (48.8s), exit 0   (real FastAPI + SQLite + Vite; outbound sockets blocked)
```
The E2E suite earned its keep: its first run exposed two S1 UI defects (login form unreachable, stale
auth banner) that the unit suite could not see. Both are fixed and the suite now passes 15/15.
The PG-backed E2E and remote CI were **not run** and are not claimed as passing.

## G. Security Report
- No S0 findings. No secret was printed, logged or written to any artifact.
- SSRF/DNS/IPv6 protections re-exercised through `tests/test_security.py` in both lanes.
- Secret-safe configuration: GET never returns secret values (`tests/test_configuration_control_plane.py`).
- Auto-purge stayed OFF; no archive was purged; no real database was touched.

## H. Performance Report
Not re-measured this execution. Prior measurements remain in `docs/F18_NPLUS1.md`,
`docs/F19_HEAVY_ENDPOINTS.md` and `docs/F23_RATE_LIMIT.md`. No speedup is claimed.

## I. Local Runbook
```bash
cp .env.example .env                 # MOCK_MODE=true
python scripts/check_env.py
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
docker compose up -d --build         # postgres :15432, backend :8000, frontend :5173, n8n :5678
python -m alembic upgrade head
cd apps/web && npm ci && npm run dev
```

## J. Configuration Guide
Providers, sources, Telegram and SMTP are configured through the Configuration Control Plane UI or
`POSTGRES_*` / `TELEGRAM_*` / `SMTP_*` environment variables. Secrets are write-only through the API
and never returned by GET. No code change is needed to rotate a credential.

## K. Backup & Recovery
`docs/BACKUP.md` and `scripts/` hold the documented `pg_dump` / restore path; verified earlier
(counts matched after restore to a separate database). The archive restore path is covered by
`tests/test_archive_restore.py`. Auto-purge remains disabled until an owner decision.

## L. Known Limitations / Blockers
| Item | Status | Needed |
|---|---|---|
| F03 live provider verification | BLOCKED_EXTERNAL | reachable provider/region or alternate key |
| F04 gold set / F-24 calibration | BLOCKED (human) | 100–200 labelled articles + adjudication |
| F12 live SMTP send | BLOCKED_EXTERNAL | `SMTP_*` credentials |
| F13 second live Telegram archive round-trip | BLOCKED_EXTERNAL | bot token + private chat |
| F16 calibration | BLOCKED (data) | resolved forecast outcomes over time |
| F-20 `topics`/`entities` Text→JSONB | OPEN (deferred) | schema migration decision |
| Multi-process rate limiting | OPEN (documented) | shared backend (Redis) if workers scale out |
| Remote CI (Python 3.12 / pytest<9) | NOT VERIFIED | one CI run on the pushed branch |
| PG-backed E2E (`test:e2e:pg`) | NOT RUN | needs the matching local PG credential; creds are never guessed |
| Restart/soak acceptance pass | NOT RUN | requires a longer local session |

## M. Final Acceptance Matrix
`docs/qa/TRACEABILITY_MATRIX.csv` (39 requirement rows, each with test reference and latest result).
Each requirement without a passing test is marked NOT RUN/BLOCKED rather than PASS.

## N. Final Verdict
`PROJECT_COMPLETE_WITH_EXTERNAL_BLOCKERS`

Local engineering acceptance passes on measured evidence; the remaining items require credentials,
human labelling, or time-series outcomes and are explicitly not claimed as complete.
