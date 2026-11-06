# ADR-008: Data contract versioning (additive)
Context: Frontend/backend contract stability.
Current State: FastAPI OpenAPI + manual TS types.
Problem: Drift risk.
Decision: Additive changes only; no breaking renames without migration plan. Consider codegen later (gap).
Consequences: Backward compat preserved.
Migration: Additive.
Rollback: Revert additive.
Tests: contract tests.
