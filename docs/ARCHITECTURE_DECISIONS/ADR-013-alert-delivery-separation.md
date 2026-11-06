# ADR-013: Alert generation vs delivery separation
Context: Alert pipeline.
Current State: Generation (rules) separate from delivery (domains/alerts/delivery.py) with retry/backoff/idempotency.
Problem: Channel coupling.
Decision: Keep separation; channel failure isolated; max attempts terminal.
Consequences: Resilient delivery.
Migration: None.
Rollback: N/A.
Tests: test_alert_delivery, test_alert_delivery_live.
