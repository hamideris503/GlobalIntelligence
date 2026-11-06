# Target Architecture — GlobalIntelligence

Status: Validated against current codebase (2026-11-05). Architecture remains **Modular Monolith + Workers** (FastAPI + React/Vite + PostgreSQL + in-process BackgroundTasks + n8n). No microservices, no new broker.

## 1. Layers (mapped to existing code)

| Layer | Owner (code) | Responsibility |
|---|---|---|
| Presentation | `apps/web/` (React 18 + Vite 5 + Tailwind 4) | App Shell, pages, components, state, API client. Display only; no business rules. |
| API | `backend/api/routers/` (45 routers) + `backend/main.py:create_app()` | Auth (X-API-Key), validation (Pydantic), request/response. |
| Application | `domains/*/` services, `backend/ai/dispatch/`, `source_bot/jobs.py` | Use cases, orchestration, job lifecycle. |
| Domain | `domains/` (30+ modules) + `backend/ai/` | Business rules, entities, policies. |
| Infrastructure | `backend/database/`, `backend/ai/providers/`, `source_bot/adapters/`, `domains/archive/` | DB repos, provider clients, source adapters, file storage. |
| Background Execution | FastAPI `BackgroundTasks`, `source_bot/jobs.py`, n8n (`integrations/n8n/workflows/`) | Heavy/async work; single owner = DispatchService + JobRun. |
| AI Platform | `backend/ai/gateway/gateway.py` (AIGateway), `backend/ai/providers/`, `backend/ai/routing/`, `backend/ai/provider_catalog.py` | Single entry point for all model execution. |
| Shared Contracts | `backend/ai/schemas/types.py`, `backend/database/models/*`, `apps/web/src/types.ts` | IDs, provenance, timestamps, status enums. |

## 2. Data flow

```
Source (source_bot) -> Document -> Article -> Event -> Claim -> Evidence
  -> Entity/Relationship -> Analysis -> World State -> Forecast -> Scenario
  -> Risk -> Decision -> Outcome -> Evaluation -> Memory
```

Conceptual chain; not a new table per step. Existing models in `backend/database/models/` own each entity.

## 3. Control flow

- All AI execution goes through `AIGateway` (no provider hard-coding in domains).
- All heavy work goes through `DispatchService` + `JobRun` (no second runner).
- All ingestion goes through `NewsIngestionPipeline` + `SourceRegistry` (no second pipeline).
- All source/provider config goes through configuration control plane (`backend/configuration/`, `backend/api/routers/configuration.py`).
- Settings secrets are write-only, encrypted (Fernet `APP_ENCRYPTION_KEY`).

## 4. External integrations (single adapter each)

n8n (pinned 2.42.6), WorldMonitor, Telegram, Email/SMTP, AI providers (mock, gemini, openai, anthropic, openrouter, local_decision, groq, cloudflare), economic/market sources. Each has one adapter with capability/input/output/auth/timeout/retry/rate-limit/error-mapping/health/metrics/provenance.

## 5. Geospatial

Shared capability, not a separate service. Current: lat/lon + bounding box + GeoJSON adapter. PostGIS NOT adopted (ADR-007) — local Windows/CI compatibility and migration cost outweigh benefit for current scale; revisit if spatial queries become hot path.

## 6. Frontend

App Shell + Design System (`apps/web/src/components/ui/*`, `design/tokens.css`, `theme.tsx`). Pages consume API via `api.ts`. RTL/Persian/dark. Tables only (no charts in v1 except map canvas).

## 7. Verification

Ruff clean, frontend typecheck/lint/build clean, backend 1548+ passed (SQLite), PG lane green. See docs/LOCAL_RUNBOOK.md.
