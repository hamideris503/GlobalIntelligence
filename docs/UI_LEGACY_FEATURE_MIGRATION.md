# Legacy Feature Migration

All existing GlobalIntelligence capabilities preserved under the new HTML-based shell. No backend/service removed.

| Capability | Old Location | Existing API/Service | New UI Location | Status | Tests |
|---|---|---|---|---|---|
| Dashboard | `pages/dashboard.tsx` | `/api/*` aggregates | `pages/dashboard.tsx` (new shell) | MIGRATED | existing |
| News | `pages/news.tsx` | `/api/news`, `/api/articles` | `pages/news.tsx` | MIGRATED | existing |
| Evidence | `pages/evidence.tsx` | `/api/claims`, `/api/evidence` | `pages/evidence.tsx` | MIGRATED | existing |
| Entity Graph | `pages/graph.tsx` | `/api/graph`, `/api/entities` | `pages/graph.tsx` | MIGRATED | existing |
| Alerts | `pages/alerts.tsx` | `/api/alerts` | `pages/alerts.tsx` | MIGRATED | existing |
| Sources | `pages/sources.tsx` | `/api/sources` | `pages/sources.tsx` | MIGRATED | existing |
| Screening | `pages/screening.tsx` | `/api/screening`, dispatch | `pages/screening.tsx` | MIGRATED | existing |
| AI Providers/Models | `pages/ai.tsx`, `pages/keys.tsx` | `/api/ai/*`, settings | `pages/ai.tsx`, `pages/keys.tsx` | MIGRATED | existing |
| Chat | `pages/chat.tsx` | `/api/chat` | `pages/chat.tsx` | MIGRATED | existing |
| World state | `pages/world.tsx` | `/api/world-state/*` | `pages/world.tsx` | MIGRATED | existing |
| Macro economy | `pages/world.tsx` | `/api/economic/*`, `/api/macro/*` | `pages/world.tsx` | MIGRATED | existing |
| Geopolitics | `pages/geo.tsx` | `/api/geopolitics/*` | `pages/geo.tsx` | MIGRATED | existing |
| Iran | `pages/geo.tsx` | `/api/iran/*` | `pages/geo.tsx` | MIGRATED | existing |
| Markets | `pages/markets.tsx` | `/api/markets/*` | `pages/markets.tsx` | MIGRATED | existing |
| Forecasts | `pages/analysis.tsx` | `/api/forecasts/*` | `pages/analysis.tsx` | MIGRATED | existing |
| Debate | `pages/debate.tsx` | `/api/debate/*` | `pages/debate.tsx` | MIGRATED | existing |
| Scenarios | `pages/analysis.tsx` | `/api/scenarios/*` | `pages/analysis.tsx` | MIGRATED | existing |
| Decisions | `pages/analysis.tsx` | `/api/decisions/*` | `pages/analysis.tsx` | MIGRATED | existing |
| Portfolio | `pages/portfolio.tsx` | `/api/portfolios/*` | `pages/portfolio.tsx` | MIGRATED | existing |
| Evaluation | `pages/portfolio.tsx` | `/api/evaluation/*` | `pages/portfolio.tsx` | MIGRATED | existing |
| History | `pages/misc.tsx` | `/api/history` | `pages/misc.tsx` | MIGRATED | existing |
| Ops/Jobs | `pages/misc.tsx` | `/api/jobs`, `/api/ops` | `pages/misc.tsx` | MIGRATED | existing |
| Archive | `pages/archive.tsx` | `/api/archive/*` | `pages/archive.tsx` | MIGRATED | existing |
| Connections | `pages/connections.tsx` | `/api/connections` | `pages/connections.tsx` | MIGRATED | existing |
| Society | `pages/society.tsx` | `/api/society/*` | `pages/society.tsx` | MIGRATED | existing |
| Settings | `pages/settings.tsx` | `/api/settings`, configuration | `pages/settings.tsx` | MIGRATED | existing |
| Search | `pages/misc.tsx` | `/api/search` | `pages/misc.tsx` | MIGRATED | existing |
| Help | `pages/misc.tsx` | static | `pages/misc.tsx` | MIGRATED | existing |

Status: All 28 capabilities migrated under new shell. No capability removed. Backend untouched.