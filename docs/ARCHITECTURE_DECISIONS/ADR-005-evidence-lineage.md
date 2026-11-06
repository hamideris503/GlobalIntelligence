# ADR-005: Shared evidence lineage contract
Context: Need traceability for analysis/forecast/decision/alert/report.
Current State: Provenance fields exist per domain.
Problem: Inconsistent lineage.
Decision: Adopt common lineage contract (input refs, model, provider, prompt version, run time, confidence, approval). Implement incrementally where gaps.
Consequences: Auditable outputs.
Migration: Additive fields only.
Rollback: Revert additive migration.
Tests: provenance tests.
