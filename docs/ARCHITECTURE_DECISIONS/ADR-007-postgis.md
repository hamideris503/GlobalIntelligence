# ADR-007: Do not adopt PostGIS now
Context: Need spatial queries.
Current State: Plain lat/lon + bbox.
Problem: PostGIS adds migration/CI/local-Windows complexity.
Options: (a) plain lat/lon+bbox; (b) PostGIS.
Decision: Keep plain lat/lon+bbox + GeoJSON adapter. Revisit if spatial queries become hot path or polygon analytics needed.
Consequences: Simpler CI/local; limited advanced spatial ops.
Migration: N/A (no change).
Rollback: N/A.
Tests: N/A.
