# Integration Control Plane — GlobalIntelligence

## Managed integrations
AI providers, news sources, economic/market sources, Telegram, notification channels (email), geographic data, external (n8n, WorldMonitor, OpenBB, TradingAgents).

## Adapter contract (per integration)
Capability, Input Contract, Output Contract, Authentication, Secret Handling (write-only, encrypted), Timeout, Retry, Rate Limit, Error Mapping, Health, Metrics, Provenance, Terms/License.

## Control plane
`backend/configuration/` + `backend/api/routers/configuration.py` + `settings.py`. UI-driven config + revision control + rollback + audit. Secrets never in browser storage or files.

## n8n
Pinned 2.42.6. `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` required. Workflows import `active:false`; keys from `$env` -> `BACKEND_API_KEY`. No hardcoded keys.

## Rules
- Two integrations must not perform the same task in parallel.
- Integration without adapter => `NEEDS_ADAPTER`.
- No anonymous code execution or free package install from UI.
