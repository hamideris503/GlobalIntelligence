# Domain Ownership — GlobalIntelligence

Rule: one owner per data/behavior. UI only displays; never re-implements business rules.

| Domain | Owner (code) | Owns |
|---|---|---|
| Source ingestion & registry | `source_bot/` (registry, adapters, jobs, runner) + `domains/news/source_registry.py` | Source, ingestion, dedup input, priority input. |
| Article / Document | `domains/news/` (`ingestion.py`, `dedup.py`) + `backend/database/models/{article,document}.py` | Article, Document, duplicate_cluster. |
| Event / Claim / Evidence | `domains/events/`, `domains/claims/` + models | Event, Claim, Evidence, verification status. |
| Entity / Relationship / Graph | `domains/entities/`, `domains/graph/` | Entity, EntityRelationship, resolution. |
| AI Platform | `backend/ai/` (gateway, providers, routing, dispatch, local_screening) | AI Run, model execution, token ledger, policy. |
| Screening | `backend/ai/local_screening/` + `domains/news` screening | Screening task, tri-state decision, human review. |
| Analysis | `domains/research/`, `domains/audit/` | Analysis runs, replay. |
| Forecast | `domains/forecast/` | Forecast runs, evaluation (Brier/LogLoss). |
| Risk / Scenario | `domains/risk/`, `domains/scenarios/` | Risk assessment, scenario, VaR/CVaR/Monte Carlo. |
| Decision | `domains/decision/` | Decision, recommendation, alternatives, audit. |
| World State / Geopolitics / Iran / Macro / Markets / Society | `domains/worldstate/`, `geopolitics/`, `iran/`, `macro/`, `markets/`, `society/` | Corresponding assessments. |
| Portfolio | `domains/portfolio/` | Portfolio, positions, snapshots. |
| Alerts | `domains/alerts/` (delivery) + alerts router | Alert rules, generation, delivery lifecycle. |
| Archive | `domains/archive/` | Archive eligibility, manifest, ZIP, Telegram, restore, purge gating. |
| Reports / Briefings | `domains/briefings/`, `domains/audit/` | Report snapshots, history. |
| Jobs / Dispatch | `backend/ai/dispatch/` + `backend/database/models/job.py` | JobRun, ArticleDispatch, retry, checkpoint. |
| Configuration / Providers / Settings | `backend/configuration/` + routers | Provider catalog, settings, secrets, revisions. |
| Geospatial | Shared (worldstate + events) | Location resolution, geometry, GeoJSON. |
| Audit / Replay | `domains/audit/` | Replay, audit records. |

## Ownership conflicts found

None material: single gateway, single ingestion pipeline, single source registry, single dispatch owner (verified by grep). No parallel implementations.
