# AI Platform Architecture — GlobalIntelligence

## Single entry point
`backend/ai/gateway/gateway.py:AIGateway` is the only model execution entry point. No domain hard-codes a provider.

## Components
- Provider Registry: `backend/ai/providers/` (mock, gemini, openai, anthropic, openrouter, local_decision, groq, cloudflare) + `provider_catalog.py`.
- Model Catalog / Capability / Eligibility: `backend/configuration/` + `backend/ai/credentials*.py`.
- Routing Policy: `backend/ai/routing/` + `backend/ai/adaptive_bootstrap.py` + `backend/ai/free_policy.py` (local providers exempt from free quota).
- AI Run: tracked via gateway run stats + `provider_run_stat.py`.
- Prompt Version: `backend/ai/prompts/`.
- Structured Output: `backend/ai/schemas/types.py`.
- Token Ledger: `backend/database/models/ai_token_ledger.py`.
- Budget: `backend/ai/budget.py`.
- Timeout/Retry/Fallback: gateway + `http_base.py`.
- Mock Provenance: flagged, never auto-deleted, rejected by classifier in prod.

## Consumers
AI Analysis, AI Chat, Debate, Evaluation, Screening, Evidence/Entity analysis, Forecasting, Scenario, Decision Support, Report Generation — all via gateway.

## Policy
No AI task runs without eligibility check. Missing provider key => provider disabled + fallback, no crash. In prod mock stripped from chain.
