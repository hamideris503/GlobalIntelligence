# ADR-012: Report snapshot reproducibility
Context: Reports must be reproducible.
Current State: Briefings + audit snapshots.
Problem: Data version tracking.
Decision: Reports store data version + analysis/evidence refs + model attribution. Reproducible from stored refs.
Consequences: Auditable reports.
Migration: Additive fields where missing.
Rollback: Revert additive.
Tests: briefing/audit tests.
