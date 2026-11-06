# ADR-009: Frontend feature boundaries
Context: Page/component growth.
Current State: Page -> components -> api -> types.
Problem: God components risk.
Decision: Keep current boundaries; split only when a page exceeds maintainability threshold. No premature splitting.
Consequences: Pragmatic.
Migration: None.
Rollback: N/A.
Tests: build/typecheck.
