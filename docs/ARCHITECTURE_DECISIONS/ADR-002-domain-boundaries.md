# ADR-002: Domain boundaries
Context: 30+ domains; risk of overlapping ownership.
Current State: One owner per data/behavior (see DOMAIN_OWNERSHIP.md).
Problem: Duplicate ownership.
Decision: Enforce single owner; UI displays only. No domain duplicates another's data.
Consequences: Clear contracts; cross-domain via IDs/FKs.
Migration: None needed; verified by grep.
Rollback: N/A.
Tests: architecture tests (import boundaries).
