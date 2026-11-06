# ADR-001: Modular Monolith remains appropriate
Context: GlobalIntelligence needs integrated domains, shared DB, single deploy.
Current State: Modular monolith + workers (FastAPI/React/PG).
Problem: Whether to split into microservices.
Options: (a) keep monolith; (b) microservices.
Trade-offs: microservices add network/ops/consistency cost with no proven need.
Decision: Keep modular monolith + workers. Revisit only if a domain needs independent scaling with evidence.
Consequences: Single deploy, shared transactions, simpler ops.
Migration: N/A.
Rollback: N/A.
Tests: existing full suite.
