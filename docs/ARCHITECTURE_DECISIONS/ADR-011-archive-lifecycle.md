# ADR-011: Archive lifecycle safety
Context: Telegram archive + purge.
Current State: Eligibility, ZIP, upload, verify, restore test; auto-purge OFF.
Problem: Data loss risk.
Decision: Purge only after remote verification + restore test + explicit owner approval. Keep AUTOMATIC_DELETION=false, PURGE_DRY_RUN=true.
Consequences: Safe retention.
Migration: None.
Rollback: N/A.
Tests: archive tests.
