# ADR-003: Job/Dispatch architecture sufficient
Context: Heavy/async ops across modules.
Current State: DispatchService + JobRun + ArticleDispatch; single owner.
Problem: Risk of second runner.
Decision: Complete existing dispatch; no new runner. Checkpoint/resume via existing fields.
Consequences: Idempotent, bounded retries, terminal states.
Migration: None.
Rollback: N/A.
Tests: test_dispatch, test_jobs.
