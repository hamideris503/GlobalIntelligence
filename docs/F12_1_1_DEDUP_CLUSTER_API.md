# F12.1.1 — dedup cluster in the API and the detail view (F-21)

**Stage:** `F12.1.1`
**Status:** `VERIFIED` (backend tests + frontend typecheck/lint/build).
**Scope source:** the delta spec file is not present in this checkout, so the stage was closed on the
F12.1 items that `docs/BASELINE_F00.md` maps to F12.1 and that need no credentials:
`F-21` (dedup cluster not in the API) is the one still open. `F-23` was already documented as done and
`F-34` already has a CI e2e job; `F-15` (AdaptiveRouter) changes runtime routing behaviour and was left
for an owner decision.

## 1. Before

| Evidence | State |
|---|---|
| `ArticleClassifiedRead` (`backend/api/routers/classify.py`) | no `duplicate_cluster` field — `docs/BASELINE_F00.md:124` |
| `GET /api/dedup/clusters` | loaded **every** `Article` row and answered per article, with no filter |
| `apps/web/src/pages/news.tsx` detail view | fetched the whole clusters table and searched it client-side for the current article |
| TASKS.md | open item: no read-model/endpoint returns cluster detail |

This was also recorded as a limitation of the UX.4 detail view.

## 2. What changed

| File | Change |
|---|---|
| `backend/api/routers/classify.py` | `duplicate_cluster: str | None = None` on `ArticleClassifiedRead` (inherited by `ArticleDetailRead`), populated in both list and detail |
| `backend/api/routers/dedup.py` | `GET /api/dedup/clusters` accepts `cluster` (server-side filter) and `limit`; rows are loaded with `selectinload(Article.document)` instead of one lazy query per row |
| `apps/web/src/pages/news.tsx` | detail view takes the cluster from the article payload and fetches `/api/dedup/clusters?cluster=…` only; the provenance list shows `خوشهٔ تکراری` |
| `apps/web/src/types.ts` | `duplicate_cluster?: string | null` on `ArticleDetail` |
| `tests/test_f12_1_1_cluster_api.py` | 4 tests |

No new dependency, no migration (the column already exists on `Article`), no change to dedup detection
itself: dedup stays *detection, not deletion*.

## 3. Contract notes

- Without parameters, `/api/dedup/clusters` keeps its previous behaviour (every article, same row shape);
  `limit` is optional and only a guard.
- `cluster` matches both places a cluster can live: the `Article.duplicate_cluster` column **and** the
  legacy `document.doc_metadata["dedup_cluster"]`. The metadata side uses a `LIKE` prefilter on the
  quoted value (with LIKE metacharacters escaped) and the final match is re-checked in Python, so a
  substring hit such as `cl-meta-2` never satisfies a `cl-meta` filter.
- `duplicate_cluster = null` means "not in any cluster" and is rendered as `—`, never as an empty string.

## 4. Verification

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | **All checks passed** |
| Stage tests | `python -m pytest tests/test_f12_1_1_cluster_api.py tests/test_dedup.py -q` | **15 passed** (6 stage + 9 dedup) |
| Related suites | `python -m pytest tests/test_dedup.py tests/test_classification.py -q` | **58 passed** (incl. the 4 above run together: 62 total, 0 failed) |
| Frontend typecheck | `npm run typecheck` | exit 0 |
| Frontend lint | `npm run lint` | exit 0 — 0 errors, 16 pre-existing `react-refresh` warnings |
| Frontend build | `npm run build` | exit 0 — `index-CEg-uBx4.js` 342.23 kB / 108.98 kB gzip |

Test coverage: list and detail return the cluster (and `null` when absent); `?cluster=cl-1` returns only
that cluster's articles and never a foreign one; an unknown cluster returns `[]`; the unfiltered call
still returns every article (backward compatibility); a cluster stored **only** in
`document.doc_metadata` is found by the filter; and a near value (`cl-meta-2`) is never returned for a
`cl-meta` filter.

## 5. Known gaps

| Severity | Gap |
|---|---|
| `LOW` | The metadata path is a text prefilter, not an indexed JSON query: a cluster that exists only in `doc_metadata` still triggers a scan of rows whose metadata contains that quoted value. A real fix is a JSON/JSONB column with an index, or backfilling `Article.duplicate_cluster` from metadata (see `F-20`). |
| `MEDIUM` | No live/browser verification of the new provenance row: the running backend (port 8000) serves the old code and restarting it is the owner's process; a throwaway local instance could not reach the PostgreSQL instance used by Docker (`connection timeout`), so UI evidence is limited to typecheck/build plus the backend API tests. |
| `LOW` | `F-15` (AdaptiveRouter has no production consumer) is still open and deliberately untouched here. |
