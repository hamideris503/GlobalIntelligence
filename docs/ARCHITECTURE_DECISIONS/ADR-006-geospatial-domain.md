# ADR-006: Geospatial as shared capability (not separate service)
Context: Multiple modules need location.
Current State: lat/lon + bbox + GeoJSON in worldstate/events.
Problem: Avoid parallel geo service.
Decision: Shared capability owned by worldstate+events; no separate service/DB.
Consequences: Reuse, no duplication.
Migration: None.
Rollback: N/A.
Tests: world/e2e tests.
