# Architecture Tests — GlobalIntelligence

## Import boundaries / layering
- Domains must not import from `apps/web`.
- `backend/ai/gateway` is the only model execution entry point (no direct provider imports in domains).
- `source_bot`/ingestion is the only ingestion path.
- Single dispatch owner: `backend/ai/dispatch`.

## Service duplication checks
- Only one `AIGateway`, one `NewsIngestionPipeline`, one `SourceRegistry`, one dispatch runner (verified by grep, 2026-11-05).

## Data integrity
- FKs, unique constraints, referential integrity, idempotency (ArticleDispatch unique per article+task).
- Temporal integrity: point-in-time fields preserved.
- Provenance: analysis/forecast/recommendation/alert/report lineage.

## AI integrity
- Mock/real separation; model & provider attribution; prompt version; token ledger; budget; timeout; fallback; structured output; eval reproducibility.

## Full product integration scenarios (A-H)
News->Decision, AI Conversation, Model Debate, Human Screening, World Intelligence, Telegram Archive (purge gated), Alert Delivery, Evaluation. Covered by existing test suite + e2e.

## Security
- SSRF/adapter security (F06), secrets write-only/encrypted, auto-purge off, no anonymous code exec.
