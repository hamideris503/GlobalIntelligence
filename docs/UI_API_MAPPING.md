# UI → API → Database → Test mapping (stage UI-00)

**Companion to:** `docs/UI_INTEGRATION_AUDIT.md`, `docs/UI_PAGE_FEATURE_MATRIX.md`
**Contract source:** `python docs/audit-baseline/dump_openapi.py` against `backend/main.py:create_app()`
→ **189 paths / 202 operations**, generated 2026-11-04.
**Warning:** the *live* container serves an older contract (`/api/archive/*`,
`/api/configuration/*` → 404). This document describes the **working tree**.

## 1. Method

1. Endpoint inventory extracted from the FastAPI app itself (not from router filenames).
2. Each prototype page/feature matched to existing operations; a feature is marked for backend work
   **only** when no operation can express it (§6).
3. Table names read from `__tablename__` in `backend/database/models/*` — every mapping below names
   a table that exists.
4. "Test" names the level that proves it: `integration` (pytest + PG), `e2e` (Playwright, existing
   configs in `apps/web/playwright*.config.ts`), `contract` (response-shape assertion).

## 2. Primary mapping

| UI feature (page) | Backend operations | Table(s) | Operations allowed | Test |
|---|---|---|---|---|
| Dashboard KPIs (`dashboard`) | `GET /api/ops/status` | `job_runs`, `documents`, `articles` | read | integration |
| Dashboard markets widget | `GET /api/markets/latest`, `/api/markets/observations` | `market_observations` | read | integration |
| Dashboard risk widget | `GET /api/risk/overview` | `risk_assessments` | read | integration |
| Dashboard world widget | `GET /api/world-state/current` | `world_states` | read | integration |
| Source health KPI | `GET /api/sources` | `sources` | read | integration |
| AI analysis (`ai`) | `GET /api/ai/providers`, `/api/ai/status`; `POST /api/ai/generate`; `GET/POST /api/ai-routing/routes`, `/apply` | `ai_providers`, `ai_models`, `ai_token_ledger`, `provider_run_stats` | read + execute | integration + e2e |
| AI chat (`chat`) | `POST /api/ai/chat`; `GET /api/settings/models`, `/providers` | `ai_providers`, `ai_models` (no conversation table) | read + execute | integration |
| Debate (`debate`) | `GET /api/debate/runs`, `/runs/{id}`; `POST /api/decisions/from-debate` | `debate_runs`, `debate_messages`, `recommendations` | read + create | e2e |
| Evaluation (`evaluation`) | `GET /api/evaluation/*`, `/api/self-eval/*`, `/api/debate/scorecard` | `model_performance`, `self_evaluations`, `provider_run_stats` | read | integration |
| **Evidence & claims (missing page)** | `GET /api/claims`, `/claims/{claim_id}/evidence`; `POST /api/claims/extract`, `/claims/evidence` | `claims`, `evidence` | read + execute | e2e |
| **Entity graph (missing page)** | `GET /api/graph/entities`, `/entities/{id}`, `/relationships`, `/neighbors/{id}`; `POST /api/graph/extract` | `entities`, `entity_relationships` | read + execute | e2e |
| Forecasts (`forecast`) | `GET /api/forecasts`, `/ledger/active`; `POST /api/forecasts/run` | `forecasts`, `forecast_outcomes` | read + execute | e2e |
| Scenarios & risk (`scenarios`) | `GET /api/scenarios`; `POST /api/scenarios/run`; `GET /api/risk/overview`; `POST /api/risk/analyze` | `scenarios`, `risk_assessments` | read + execute | e2e |
| Decisions (`decisions`) | `GET /api/decisions`; `POST /api/decisions/run`; `GET /api/audit/log` | `recommendations`, `audit_records` | read + execute | e2e |
| Inbox (`news`) | `GET /api/classify/articles`, `/classify/articles/{id}`, `/api/events`, `/api/claims` | `articles`, `documents`, `events`, `claims` | read | e2e |
| Duplicate clusters (`UX-12`) | `GET /api/dedup/clusters`; `POST /api/dedup/run` | `articles.duplicate_cluster` (column, no cluster table) | read + execute | integration |
| World state (`world`) | `GET /api/world-state/current`, `/history`; `POST /api/world-state/build` | `world_states` | read + execute | integration |
| **World map (missing)** | **none** — 0 coordinate fields; needs `G-2`/`D-1` | `articles.country`, `entities.country` (ISO-2) | read (aggregate) | e2e |
| Geopolitics (`geo`) | `GET /api/geopolitics/tensions`, `/assessments`; `POST /api/geopolitics/analyze` | `geopolitical_assessments` | read + execute | integration |
| Iran (`iran`) | `GET /api/iran/brief`, `/transmission`, `/events`; `POST /api/iran/transmission/analyze` | `transmission_assessments`, `events` | read + execute | integration |
| Macro (`macro`) | `GET /api/macro/overview`, `/assessments`; `POST /api/macro/analyze`; `GET/POST /api/economic/*` | `macro_assessments`, `macro_observations`, `market_observations` | read + execute | integration |
| Markets (`markets`) | `GET /api/markets/symbols`, `/latest`, `/observations`; `POST /api/markets/fetch` | `market_observations` | read + execute | integration |
| Portfolio (`portfolio`) | `GET /api/portfolios`, `/portfolios/{id}/snapshots` | `portfolios`, `portfolio_snapshots` | read + create | e2e |
| Screening (`screening`) | `GET /api/screening/queue`; `POST /api/screening/review/{id}/ack`; `GET /api/local-runtimes/status` | `articles` (classification_meta), dispatch tables | read + update | e2e |
| Dispatch / retry | `GET /api/dispatch/jobs`; `POST /api/dispatch/{id}/retry` | `article_dispatches` | read + control | integration |
| Sources (`sources`) | `GET /api/sources`, `POST /api/sources`, `PATCH /api/sources/{id}`, `/sources/{id}/recheck`; `POST /api/ingest`, `/ingest/all`; `GET /api/sources/export/all` | `sources`, `documents` | CRUD + execute | e2e |
| Providers (`providers`) | `GET /api/ai/providers`, `/ai/status`; `GET/POST /api/settings/providers`, `/models`; `GET/POST /api/configuration/instances`, `/definitions`, revisions `validate/test/activate/rollback` | `ai_providers`, `ai_models`, `ai_settings`, `configuration_instances`, `configuration_revisions` | CRUD + control (secrets masked) | e2e |
| Operations (`ops`) | `GET /api/jobs`, `/api/ops/monitoring`; `POST /api/memory/archive` | `job_runs`, `memory_records` | read (+archive) | e2e |
| Alerts (`ops` tab; no page) | `GET /api/alerts`, `/alerts/{id}`; `POST /{id}/ack`, `/{id}/resolve`, `/{id}/deliver/{channel}`, `/deliver/pending`, `/evaluate`; `GET/POST /api/alerts/rules`, `PATCH /rules/{id}` | `alerts`, `alert_rules`, `alert_deliveries` | read + update + deliver | e2e |
| Archive (`archive`) | `GET /api/archive/catalog`, `/catalog/{id}`, `/settings`, `/storage`, `/purge/preview`; `POST /validate`, `/restore`, `/restore/dry-run`, `/telegram/{id}` | `archive_catalog`, `archive_articles` | read + control (gate enforced server-side) | integration (**live 404** — `B-1`) |
| Reports (`history`) | `GET /api/briefings`, `/{id}`; `POST /api/briefings/daily`, `/weekly`; `GET /api/audit/log` | `briefings`, `audit_records` | read + create | e2e |
| Settings (`settings`) | `GET/POST /api/settings/{app,models,providers,diversity,agent-assignments,import-from-env}`; model verify/block; `/api/configuration/*` | `app_settings`, `ai_settings`, `agent_assignments`, `configuration_instances` | CRUD (validated, audited) | e2e (**config live 404**) |
| Society (`society`) | `GET /api/society/mood`, `/assessments`; `POST /api/society/analyze` | `social_assessments`, `narratives` | read + execute | integration |
| Search (`search`) | `GET /api/classify/articles`, `/api/events`, `/api/sources`, `/api/briefings` | overlapping with above | read | e2e |
| Notifications (shell) | `GET /api/alerts?status=active`, `/api/ops/monitoring` | `alerts`, `job_runs` | read | e2e |

Every row maps to a table that exists; no row assumes an endpoint that is absent. Two rows
(*World map*, *Alerts page*) are marked as UI work over **existing** or **absent** capability
respectively — the distinction is explicit.

## 3. Operations the UI does **not** use (available, unexposed)

Evidence that the backend is ahead of the UI — these are integration opportunities, not bugs:

| Group | Unused operations |
|---|---|
| Evidence | `GET /api/claims/{claim_id}/evidence`, `POST /api/claims/extract`, `POST /api/claims/evidence` (only partly used) |
| Graph | all 5 `/api/graph/*` |
| Dedup | `GET /api/dedup/clusters` |
| Alerts | `GET/POST /api/alerts/rules`, `PATCH /rules/{id}`, `POST /{id}/resolve`, `POST /{id}/deliver/{channel}`, `POST /alerts/deliver/pending` |
| Archive | `GET /api/archive/catalog/{id}`, `POST /telegram/{id}` (page exists, stack stale) |
| Configuration | all 10 `/api/configuration/*` |
| Analysis depth | `/api/analogues/*`, `/api/learning/*`, `/api/tournaments/*`, `/api/independence/*`, `/api/performance/*`, `/api/outcomes/*`, `/api/narratives/*`, `/api/research/graphrag`, `/api/memory/*` |
| Ingestion extras | `/api/ingest` variants (6), `/api/dispatch/*` (6) |

## 4. Pagination / filtering gaps

| Need | Endpoint | Missing |
|---|---|---|
| Paged inbox | `/api/classify/articles` | `offset`, total |
| Paged claims list | `/api/claims` | `offset`, total |
| Paged events | `/api/events` | `offset`, total |
| Paged forecasts | `/api/forecasts` | `offset`, total |
| Paged alerts | `/api/alerts` | `offset`, total |
| Paged jobs | `/api/jobs` | `offset`, total |
| Server-side sort | all list endpoints | no `sort`/`order` parameter anywhere |
| Date-range filter | articles/events/claims | no `from`/`to` parameters |

Adding `offset` + a total is **backward compatible** (`limit` semantics unchanged) and is the single
cheapest backend change that unblocks real pagination on five pages (`G-1`).

## 5. Response-shape notes that constrain the UI

1. **No `total` field in any schema** — the UI must not print "از N" unless the backend supplies it.
   Today the dashboard derives counts client-side from `limit=200` lists (`UX-19`); any such number
   must be labelled as *"از میان اولین N رکورد"* until `G-4`.
2. **`importance` is inverted** (1 = highest, 10 = lowest) — `format.ts:importanceLabel` already
   states this; new surfaces must reuse it instead of rendering the raw number (`UX-04`).
3. **`evidence.direction`** is the string `supports|contradicts` — the evidence page must branch on it,
   and must not coerce unknown values to "supporting".
4. **`Article.country` is ISO-2, `MarketObservation.country` is ISO-3** — a map or filter joining them
   must not assume one code space.
5. **Secrets**: provider/settings responses must be checked for masked-only keys before the providers
   surface is built; no new endpoint may return a stored credential.

## 6. Backend work actually required (minimum, proven absent)

| ID | Change | Why the UI cannot work around it | Migration? |
|---|---|---|---|
| `G-1` | `offset` param + total on 6 list endpoints | filtering a truncated client list is not pagination | no |
| `G-2` | Aggregate read endpoint for map counts (per `D-1` option a) **or** `Event.latitude/longitude` (option b) | no coordinates exist anywhere | option a: no; option b: **yes** |
| `G-4` | One aggregate KPI endpoint (counts + `last_updated_at`) | client-side counts over `limit=200` are not totals | no |
| `G-5` | none — `/api/society/*` already exists | page is simply unconnected | no |

`G-3` (live 404 for archive/configuration) is **not** a code change — it is a stale image (`B-1`).

Nothing else in the 202-operation contract was found missing for the 25 prototype pages. In
particular the "big" features — evidence, entity graph, alerts rules/delivery, duplicate clusters,
configuration revisions — are **already implemented server-side** and are purely UI work.

## 7. How to re-generate this evidence

```bash
python docs/audit-baseline/dump_openapi.py          # 189 paths / 202 operations
python docs/audit-baseline/dump_openapi.py --json   # full document for contract tests
```

Re-run after any router change; a diff of the two outputs is the cheapest API-contract regression
check available without new dependencies.
