# Job & Workflow Architecture — GlobalIntelligence

## Single owner
`backend/ai/dispatch/` (routing/service/runner) + `backend/database/models/job.py` + `backend/database/models/article_dispatch.py`. No second runner.

## Job contract
Job ID, Job Type, Status, Priority, Input Reference, Idempotency Key, Attempt, Max Attempts, Retry Policy, Started/Finished At, Error, Checkpoint, Worker, Cancellation, Result Reference, Provenance.

## Dispatch idempotency
One `ArticleDispatch` row per `(article_id, task_name)`. Only `pending/retryable` due rows claimable. Retries bounded; terminal end state. Idempotent.

## Heavy/async consumers
Ingestion, Screening, Analysis, Debate, Evaluation, Forecast, Scenario, Report, Alert Delivery, Archive, Restore, Provider Health Check — all via dispatch/jobs.

## Recovery
Checkpoint + resume (`docs/F17_RESUME.md`), cancellation, dead-letter handling. Retry/backoff in alert delivery and dispatch.

## Observability
`backend/api/routers/jobs.py`, `ops.py`, `monitoring.py`; structured logs; metrics in `source_bot/metrics.py`.
