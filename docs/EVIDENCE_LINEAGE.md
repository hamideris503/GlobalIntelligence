# Evidence Lineage — GlobalIntelligence

## Chain
Source -> Document -> Article -> Event -> Claim -> Evidence -> Entity -> Relationship -> Analysis -> World State -> Forecast -> Scenario -> Risk -> Decision -> Outcome -> Evaluation -> Memory.

## Tracking requirements (per Analysis/Forecast/Recommendation/Alert/Report)
- Exact inputs (article IDs, event IDs, evidence IDs, entity IDs).
- Model + provider + prompt version.
- Confidence calculation method.
- Run time + human approval flag.
- Data version / snapshot.

## Provenance fields
`published_at/retrieved_at/available_at/observed_at/revision_at`, source_id, content_hash, hash. Unique per source `(source_id, hash, content_hash)` — never global (preserves independence signal).

## Corroboration
`corroborated` requires >=2 independent sources (not mentions). Dedup = stdlib shingling+MinHash+LSH+Union-Find, detection not deletion (`duplicate_cluster`).
