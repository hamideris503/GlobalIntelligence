# UX-01 (BLOCKER) — "test fetch" no longer ingests

**Finding:** `docs/UI_UX_AUDIT.md` `UX-01` — the "دریافت آزمایشی" action on a source called
`POST /api/ingest`, so a *preview* silently wrote `Document`/`Article` rows and moved ingestion counters.
That breaks the project rule "preview never ingests" (`docs/DELTA_IMPLEMENTATION_INVENTORY.md` 2.6) and
pollutes data.

**Status:** `VERIFIED` — the action is now a read-only preview; the ingesting call is gone from the UI.

## 1. What changed

| File | Change |
|---|---|
| `backend/api/routers/sources.py` | new `POST /api/sources/{id}/preview?limit=N` → resolves the source's plan (honouring the pinned configuration revision, 2.7) and calls `backend.configuration.preview.preview_fetch` |
| `apps/web/src/pages/sources.tsx` | `trialFetch` posts to the preview endpoint; the button label is now «پیشنمایش (بدون ذخیره)» and the result line ends with «ذخیره نشد» |
| `tests/test_source_preview_api.py` | 5 tests |

The endpoint reuses the preview path built in F03.0: `connection_check` (scheme / userinfo / DNS / private
IP), the same adapter registry, and sanitized samples (`url_origin` only, truncated title/summary,
`content_sha256` prefix). No second fetcher and no new dependency were introduced.

Response shape:

```json
{"source_id": "...", "source_name": "...", "adapter": "rss", "url_origin": "https://example.com",
 "count": 2, "samples": [{"title": "...", "summary": null, "content_chars": 4,
 "content_sha256": "aaa", "published_at": null}], "ingested": false, "config_revision": null}
```

Errors: `404` unknown source; `422` when the source resolves to `skip`/`specialized` (with the reason), or
when the adapter has no preview path (`csv`, `xml`, `html`, `rest_json`), or when the connection policy
rejects the URL.

## 2. Verification

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | All checks passed |
| Preview + pin tests | `pytest tests/test_source_preview_api.py tests/test_config_revision_pin.py -q` | **10 passed** |
| Frontend typecheck | `npm run typecheck` | exit 0 |
| Frontend lint | `npm run lint` | exit 0 — 0 errors, 16 pre-existing `react-refresh` warnings |
| Frontend build | `npm run build` | exit 0 — `index-CVLaBHsH.js` 342.33 kB / 109.03 kB gzip |
| Regression suites | `pytest tests/test_sources.py tests/test_security.py tests/test_ingest_jobs.py -q` | see the stage report |

The key assertions in `tests/test_source_preview_api.py`:

- the preview returns `ingested: false` **and** the `Document` count is unchanged before/after the call;
- with an active configuration revision the preview fetches the **pinned** URL and reports
  `config_revision: 1` (preview and the real run see the same config);
- a source with no usable endpoint returns `422` with the `skip` reason;
- a CSV source returns `422` "preview is not supported" instead of pretending to have fetched;
- an unknown source id returns `404`.

## 3. Remaining limits

| Severity | Gap |
|---|---|
| `LOW` | Preview is capped at `limit ≤ 20` items and does not render per-item body text; it is a sanity check, not a full reader. |
| `LOW` | `specialized` sources (macro/market fetchers) intentionally have no preview; the endpoint says so with `422` rather than showing an empty list. |
| `MEDIUM` | The other half of the audit entry — adapter-driven fields and validate→test→preview **inside the source form/wizard** (`UX-01` fix note, inventory 3.2) — is not part of this change; the control-plane API exists, the wizard does not. |
