# Module Capability Matrix — GlobalIntelligence

Status legend: `EXISTS_AND_VERIFIED` (tested), `EXISTS_BUT_INCOMPLETE`, `NEEDS_INTEGRATION`, `NEEDS_PROVIDER`, `BLOCKED`.

| Module (HTML id) | Frontend page | Backend routers | DB models | Provider | Jobs | Tests | Status |
|---|---|---|---|---|---|---|---|
| overview | dashboard.tsx | health, monitoring, briefings | briefing, world_state | mock | n/a | yes | EXISTS_AND_VERIFIED |
| ai-analysis | analysis.tsx | ai, research, audit | ai run (via gateway) | mock/real | dispatch | yes | EXISTS_AND_VERIFIED |
| ai-chat | chat.tsx | ai, memory | memory | mock/real | n/a | yes | EXISTS_AND_VERIFIED |
| debate | debate.tsx | debate, tournaments | debate | mock/real | dispatch | yes | EXISTS_AND_VERIFIED |
| evaluation | ai/eval (misc) | evaluation, selfeval | model_performance, self_evaluation | mock/real | n/a | yes | EXISTS_BUT_INCOMPLETE (human gold set pending) |
| evidence | evidence.tsx | claims, events | claim, evidence | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| entity-graph | graph.tsx | graph, entities | entity | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| forecasts | (misc/analysis) | forecasts, outcomes | forecast | mock/real | dispatch | yes | EXISTS_BUT_INCOMPLETE (F16 eval not started) |
| risk | (misc) | risk, scenarios | risk_assessment, scenario | mock/real | dispatch | yes | EXISTS_AND_VERIFIED |
| decisions | (misc) | decisions, recommendations | recommendation | mock/real | n/a | yes | EXISTS_AND_VERIFIED |
| inbox | news.tsx | ingestion, dedup, dispatch, screening | article, document | n/a | dispatch | yes | EXISTS_AND_VERIFIED |
| world | world.tsx | worldstate, events | world_state | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| geopolitics | geo.tsx | geopolitics | geopolitical_assessment | mock/real | n/a | yes | EXISTS_AND_VERIFIED |
| iran | (geo) | iran, transmission | transmission_assessment | mock/real | n/a | yes | EXISTS_AND_VERIFIED |
| macro | (misc) | macro, economic | macro_assessment | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| markets | markets.tsx | markets, macro | market | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| portfolio | portfolio.tsx | portfolios | portfolio | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| screening | screening.tsx | screening, classify, local_runtimes | (screening meta in article) | local (Kev/Laya) | dispatch | yes | EXISTS_AND_VERIFIED (calibration pending) |
| sources | sources.tsx | sources, configuration | source | n/a | ingestion | yes | EXISTS_AND_VERIFIED |
| providers | keys.tsx, connections.tsx | configuration, ai_routing, local_runtimes | configuration, ai_settings | real | n/a | yes | EXISTS_AND_VERIFIED (live providers blocked by creds/region) |
| operations | (misc) | jobs, ops, dispatch, monitoring | job, article_dispatch | n/a | dispatch | yes | EXISTS_AND_VERIFIED |
| alerts | alerts.tsx | alerts | alert, alert_delivery | Telegram/SMTP | delivery | yes | EXISTS_BUT_INCOMPLETE (SMTP live blocked) |
| archive | archive.tsx | archive | archive_catalog | Telegram | archive | yes | EXISTS_BUT_INCOMPLETE (auto-purge OFF) |
| reports | (misc) | briefings, audit | briefing | mock/real | n/a | yes | EXISTS_AND_VERIFIED |
| settings | settings.tsx | settings, configuration | configuration | n/a | n/a | yes | EXISTS_AND_VERIFIED |
| worldmap (2D) | world.tsx (canvas) | worldstate, events | event (lat/lon) | n/a | n/a | yes | EXISTS_AND_VERIFIED |

Visualization inventory: dashboard synthesis, evidence flow, mini entity network, entity graph, risk trend charts, model consensus, debate comparison, evaluation charts, forecast fan, scenario viz, risk matrix, portfolio allocation, pipeline flow, source health, provider status, alert timeline, archive health, historical trends, world map + heatmap + clusters + lines + polygons. All backed by real API data (no hardcoded operational counters) per F14/F19 verification; some charts (fan chart) are UI-only rendering of API data.
