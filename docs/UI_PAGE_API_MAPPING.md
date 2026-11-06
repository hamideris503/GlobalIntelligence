# UI Page → API Mapping

| UI Page | Key API Endpoints | Backend Router | Database Entity |
|---|---|---|---|
| Dashboard | `/api/*` aggregates, `/health` | health, monitoring | various |
| News | `/api/news`, `/api/articles` | ingestion, claims | Article, Source |
| Evidence | `/api/claims`, `/api/evidence` | claims, dedup | Claim, Evidence |
| Entity Graph | `/api/graph`, `/api/entities` | graph, entities | Entity, Relation |
| Alerts | `/api/alerts` | alerts | Alert, AlertDelivery |
| Sources | `/api/sources` | sources | Source |
| Screening | `/api/screening`, `/api/dispatch` | screening, dispatch | ArticleDispatch |
| AI | `/api/ai/*` | ai, ai_routing | Provider, Model |
| Keys | `/api/settings`, configuration | settings, configuration | ApiKey (encrypted) |
| Chat | `/api/chat` | ai | Conversation |
| World | `/api/world-state/*` | worldstate | WorldState |
| Macro | `/api/economic/*`, `/api/macro/*` | economic, macro | MacroObservation |
| Geopolitics | `/api/geopolitics/*` | geopolitics | GeoEvent |
| Iran | `/api/iran/*` | iran | IranIndicator |
| Markets | `/api/markets/*` | markets | MarketQuote |
| Forecasts | `/api/forecasts/*` | forecasts | Forecast |
| Debate | `/api/debate/*` | debate | Debate |
| Scenarios | `/api/scenarios/*` | scenarios | Scenario |
| Decisions | `/api/decisions/*` | decisions | Decision |
| Portfolio | `/api/portfolios/*` | portfolios | Portfolio |
| Evaluation | `/api/evaluation/*` | evaluation | Evaluation |
| History | `/api/history` | audit | AuditLog |
| Ops | `/api/jobs`, `/api/ops` | jobs, ops | JobRun |
| Archive | `/api/archive/*` | archive | ArchiveCatalog |
| Connections | `/api/connections` | configuration | Connection |
| Society | `/api/society/*` | society | SocietySignal |
| Settings | `/api/settings`, configuration | settings, configuration | Setting |
| Search | `/api/search` | search | — |
| Help | static | — | — |

No endpoint duplicated. All reuse existing routers. No fake API created.