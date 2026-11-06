# ADR-014: Dashboard aggregation layer
Context: Overview needs cross-module summary.
Current State: Dashboard reads real APIs.
Problem: Avoid analysis in dashboard.
Decision: Aggregation layer only reads/summarizes/links; no analysis logic or independent DB.
Consequences: Thin dashboard.
Migration: None.
Rollback: N/A.
Tests: dashboard tests.
