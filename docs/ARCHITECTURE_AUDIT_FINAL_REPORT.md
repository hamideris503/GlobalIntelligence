# Architecture Audit Final Report — GlobalIntelligence

Date: 2026-11-05. Branch: `stage95-pg-ci-verification`, HEAD `42b2278e22deb19119bb8447db00bcaad4b549fb`. Working tree preserved (no commits/pushes).

## 1. Current Architecture Verdict

### Strengths
- Modular monolith + workers with clear domain folders (`domains/`, 30+ modules).
- Single AI Gateway (`backend/ai/gateway/gateway.py:AIGateway`) — verified only one Gateway class in project code.
- Single ingestion pipeline (`domains/news/ingestion.py:NewsIngestionPipeline`) and single source registry.
- Single dispatch owner (`backend/ai/dispatch/` + `JobRun`/`ArticleDispatch`) with idempotency.
- Configuration control plane with write-only encrypted secrets, revision control, rollback, audit.
- Strong test baseline: ruff clean, frontend typecheck/lint/build clean, backend 1548 passed/1 skipped (SQLite), PG lane green.
- Mock-first with provenance; auto-purge off by default; archive/restore verified.

### Weaknesses / gaps
- Frontend types manually synced with OpenAPI (no codegen) — drift risk (P2).
- Live providers blocked by credentials/region/terms (external).
- Human gold set / threshold calibration pending (external human input).
- Forecast evaluation (F16) not started (needs real forecast + outcome tracking).
- SMTP live send blocked (no creds); Telegram live verified.
- Remote CI (Python 3.12/pytest<9) unverified (environment unavailable).

### Sufficient (no change needed)
- Modular monolith, domain boundaries, job architecture, AI execution, geospatial (plain lat/lon+bbox), alert delivery separation, dashboard aggregation, archive lifecycle safety.

### Incomplete (external/input-blocked)
- Evaluation calibration, forecast evaluation, live provider verification, full soak/E2E.

### Necessary fixes implemented this mission
- None code-level: architecture already clean (no duplicate services found). Added documentation set (target architecture, ownership, capability matrix, shared contracts, AI platform, job/workflow, evidence lineage, geoint, integration control plane, frontend platform, local runbook, architecture tests, 14 ADRs) and ARCHITECTURE.md pointer.

### Unnecessary (avoided)
- No microservices, no Kafka/Redis/K8s, no second pipelines/gateways/registries, no PostGIS, no rewrite.

## 2. Full Product Capability Matrix
See `docs/MODULE_CAPABILITY_MATRIX.md`. All 25 HTML modules (overview, ai-analysis, ai-chat, debate, evaluation, evidence, entity-graph, forecasts, risk, decisions, inbox, world, geopolitics, iran, macro, markets, portfolio, screening, sources, providers, operations, alerts, archive, reports, settings) plus WorldMonitor 2D map are implemented; statuses: most `EXISTS_AND_VERIFIED`, a few `EXISTS_BUT_INCOMPLETE` (evaluation, forecasts, alerts, archive) due to external blockers.

## 3. Architecture Gap Register
| ID | Description | Severity | Root cause | Fix | Status |
|---|---|---|---|---|---|
| GAP-01 | OpenAPI→TS manual sync | P2 | No codegen | Add codegen (future) | Open |
| GAP-02 | Live provider verification | P1 | Credentials/region/terms | Provide creds | Blocked (external) |
| GAP-03 | Human gold set / calibration | P1 | Human labeling | Annotators | Blocked (external) |
| GAP-04 | Forecast evaluation (F16) | P2 | Needs real forecast+outcome | Run tracking | Open |
| GAP-05 | SMTP live send | P2 | No SMTP creds | Provide creds | Blocked (external) |
| GAP-06 | Remote CI verification | P2 | No CI env | Run in CI | Open |
| GAP-07 | F14 remaining subitems | P3 | Verification tasks | Profile/migrate | Open |

## 4. Target Architecture
See `docs/TARGET_ARCHITECTURE.md`. Modular monolith + workers retained; layers mapped to existing code; data flow chain defined; geospatial plain lat/lon+bbox (ADR-007).

## 5. ADR Register
14 ADRs in `docs/ARCHITECTURE_DECISIONS/` (ADR-001..ADR-014): monolith, domain boundaries, job arch, AI execution, evidence lineage, geospatial shared, no PostGIS, contract versioning, frontend boundaries, control plane, archive safety, report snapshot, alert separation, dashboard aggregation.

## 6. Changes Implemented
- Files created: 12 docs + 14 ADRs + this report (27 files).
- Files modified: `ARCHITECTURE.md` (pointer appended).
- Modules reused: all (no new services).
- APIs changed: none.
- DB changes: none.
- Migration changes: none.
- Tests added: none (no new logic; documentation only).

## 7. Verification Results
- `ruff check backend domains tests scripts source_bot` → exit 0 (All checks passed).
- `npm run typecheck` → exit 0.
- `npm run lint` → exit 0 (0 errors, 7 warnings).
- `npm run build` → exit 0 (1963 modules, 361.96 kB JS).
- `cd backend && python -m pytest ... (subset)` → 53 passed, 1 skipped.
- Import check: `backend.main` imports OK.
- Full suite historically: 1548 passed/1 skipped (SQLite); PG lane green.

## 8. Remaining Work
External blockers: provider creds/region/terms, human gold-set labeling, SMTP creds, remote CI env. Open items: codegen, F16 forecast eval, F14 subitems, full soak/E2E.

## 9. Final Status
`ARCHITECTURE_VALIDATED_NO_MAJOR_CHANGE_NEEDED` — architecture is sound, no duplicate/parallel services, no major refactor required; only documentation added and external-blocked items remain.
