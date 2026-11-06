# F18 — N+1 و خواندن تمام‌جدولی (F-18)

**وضعیت:** NOT_STARTED (نیاز به اندازه‌گیری) · **تاریخ:** 2026-10-29

## English summary

F-18 requires profiling before optimization. Candidate hotspots identified in code:
- `domains/research/graphrag.py::_resolve` (per-key SELECT on Entity) and `retrieve` (per-entity `db.get` in the BFS loop).
- `domains/audit/replay.py` fingerprints whole tables.
- `domains/macro/*`, `domains/risk/*`, etc. engines (`analyze_all`).

No index/batching change was made without measurement, per F-18's own rule. `_adjacency()` already
loads all `EntityRelationship` rows in one query (not N+1). Optimization deferred until a real dataset
and query profile exist.

## ۱) محدودیت صریح

- بدون دادهٔ واقعی، بهینه‌سازی کور ممنوع است (F-18).
- هر تغییر باید با تست «عدم تغییر معنای خروجی» همراه باشد.
- F-19 (heavy endpoints) هم نیاز به اندازه‌گیری دارد.


## Measurement update 2026-11-01 (F14/F15-E)

Profiling via SQLAlchemy before_cursor_execute on PG (conftest engine):
- POST /api/ingest: 26 queries, 0.051s (3 articles)
- POST /api/dedup/run: 6 queries, 0.024s
- POST /api/classify/run: 106 queries, 0.183s (3 articles, ~34/article) -> N+1 candidate
- GET /api/classify/articles: 2 queries, 0.019s
- GET /api/events: 1 query, 0.011s

Conclusion: classify/run shows N+1 pattern (~34 queries/article). No optimization applied (F-19 rule: measure first; move only if proven time/cost/timeout justifies). Other endpoints within acceptable range.
