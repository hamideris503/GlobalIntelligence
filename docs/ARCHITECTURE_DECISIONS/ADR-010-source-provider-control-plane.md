# ADR-010: Source/Provider control plane
Context: Config management.
Current State: backend/configuration + routers + UI.
Problem: Secret handling.
Decision: UI-driven config with revision control, write-only encrypted secrets, rollback, audit. No secrets in browser storage/files.
Consequences: Secure config.
Migration: Existing migration a7f3c9d1e2b4.
Rollback: downgrade migration.
Tests: test_configuration_control_plane.
