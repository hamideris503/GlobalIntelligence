# Geospatial (GEOINT) Architecture — GlobalIntelligence

## Decision: ADR-007 — No PostGIS (yet)
Rationale: current needs are point + bounding-box + GeoJSON. PostGIS adds migration/CI/local-Windows complexity without proven benefit. Revisit if spatial queries become hot path or polygon/line analytics needed.

## Current capabilities
- Location, Geographic Entity, Point (lat/lon), Bounding Box Query, Spatial Filtering, GeoJSON adapter (coord order: [lon, lat]).
- Resolution method + spatial confidence + source provenance + temporal validity recorded.

## Accuracy rules
- Event location != article mentioned location.
- Org HQ location != event location.
- Country centroid is not event location.
- No fabricated coordinates; records without coords are retained (not dropped).
- GeoJSON coord order is [longitude, latitude].

## Consumers
World Monitor, Geopolitics, Iran, Event Analysis, Country Profile, Risk, Infrastructure, Maritime, Aviation, Scenario, Alert, Entity Graph.

## Shared ownership
Worldstate + events domains own resolution/geometry; no separate geo service.
