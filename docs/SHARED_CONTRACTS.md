# Shared Contracts — GlobalIntelligence

## Identifiers
- Primary keys: integer surrogate `id`. External refs use stable IDs where present (article_id, event_id, entity_id).
- All cross-domain references are FK-backed (see models).

## Timestamps (point-in-time)
- `published_at`, `retrieved_at`, `available_at`, `observed_at`, `revision_at` recorded where applicable.
- Backtests use walk-forward/rolling only; no random shuffle.

## Status conventions
- Job: `pending | running | succeeded | failed | retryable | terminal | cancelled`.
- Screening: `relevant | irrelevant | uncertain`.
- Dispatch row: one per `(article_id, task_name)`; claimable only `pending/retryable` due.
- Archive purge: gated; `AUTOMATIC_DELETION=false`, `PURGE_DRY_RUN=true`.

## Pagination / filtering
- Standard query params: `limit`, `offset`, `q`, domain-specific filters. See routers.

## Error contract
- FastAPI HTTPException with `detail`. Frontend maps to toast + empty/error states.

## Mock/Real metadata
- `MOCK_MODE` flag; mock results flagged in `classification_meta` / provider run stats; never auto-deleted; classifier rejects mock in prod.

## Provenance
- Every analysis/forecast/recommendation/alert/report tracks: input refs, model, provider, prompt version, run time, confidence, human approval flag.

## OpenAPI/TS
- FastAPI generates OpenAPI; frontend types in `apps/web/src/types.ts` (manual sync). No codegen pipeline yet (gap: add generated types in future).
