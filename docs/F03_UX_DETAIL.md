# F03.UX.4 — Article / Intelligence detail

**Stage:** `F03.UX.4`
**Status:** `VERIFIED` for the detail structure, priority vocabulary, provenance, per-task
processing state and duplicate-cluster navigation, all measured in a browser against the built app.
`PARTIALLY_VERIFIED` overall: priority **reason codes** do not exist in the article API, so the
section states that explicitly instead of inventing reasons.
**Scope:** article detail view only. No API/DB/migration change, no new dependency.

---

## 1. Before (evidence)

From `docs/UI_UX_AUDIT.md` §2 and `UX-04`/`UX-11`/`UX-12`:

- Priority was printed as a raw value (`{art.data.priority ?? "—"}`) with no P0–P4 vocabulary.
- Provenance was a flat `<dl>`; the canonical URL was hidden behind "باز کردن در زبانهٔ جدید" so the
  actual source address was not copyable.
- The detail had **no** processing state, no duplicate-cluster link, and no way to see why the item
  was classified the way it was (`decided_by` was not rendered even though the API returns it).
- Duplicate clusters had no UI anywhere in the app.

## 2. What the API actually offers (checked before building)

| Need | Source | Reality |
|---|---|---|
| Priority P0–P4 | `GET /api/classify/articles/{id}` → `priority` (`PriorityLevel`) | exists (`backend/api/routers/classify.py`) |
| Decision origin | same payload → `decided_by` (`rules` / `ai` / `small_model`) | exists but was unrendered |
| Confidence / importance / sentiment / stance | same payload | exist |
| Reason codes for the priority | — | **not in this payload** (review reasons live in the screening queue) |
| Provenance | `source_name`, `url`, `published_at`, `retrieved_at`, `language`, `country`, `id`, `event_id` | exist |
| Processing state | `GET /api/dispatch/articles/{id}` → `dispatches[] {task, status, attempts, last_error, next_retry_at}` + `screening` | exists; **no timestamps** in this read model |
| Duplicate cluster | `GET /api/dedup/clusters` → `{article_id, document_id, source_id, cluster}` | exists (all articles, client-side match) |

## 3. New structure (matches the spec's decision order)

1. Title, `PriorityBadge` (P0–P4 **with text**), classification status badge, mock tag, provider.
2. Summary, with an explicit "خلاصه‌ای ثبت نشده است" when absent.
3. **منبع و provenance**: source, the real URL as a copyable `ltr` link, published/retrieved times,
   language/country, internal id, topics, entities, related event id.
4. **چرا این اولویت؟**: priority, analytic importance (1–10 with its documented direction), decision
   origin (`rules` → «قواعد قطعی» …), confidence, sentiment/stance — plus an explicit note that the
   API exposes no reason codes, so none were fabricated.
5. **وضعیت پردازش**: per-task table (status as Persian text + tone, attempts, next retry, sanitized
   last error), a raw scalar view of the `screening` payload, and a link to `/ops` for real
   timestamps (which this endpoint does not provide).
6. **خوشهٔ تکراری**: cluster id, sibling count, sibling links that navigate to the other article, or
   an explicit "no cluster" state; note that dedup is detection, not deletion.
7. Claims of the related event (unchanged).

## 4. Verification

```bash
cd apps/web && npm run typecheck    # exit 0
cd apps/web && npx eslint src/pages/news.tsx src/types.ts   # exit 0
cd apps/web && npm run build        # exit 0, JS 341.94 kB (108.83 kB gzip)
npm run preview -- --port 4173 --strictPort
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-detail.mjs   # exit 0
```

Measured output (test-only fixtures via request interception):

```
h2: خبر نمونه برای بازبینی
priority badges: [{"text":"P1","level":"P1"},{"text":"P1","level":"P1"}]
provenance keys: منبع، پیوند اصلی، انتشار، دریافت، زبان / کشور، شناسهٔ داخلی، موضوعات،
                 موجودیت‌ها، رویداد مرتبط، اولویت دریافت، اهمیت تحلیلی، منشأ تصمیم، اطمینان، احساس / موضع
dispatch rows: 2 | cluster buttons: ["a2"] | screening heading: ["نتیجهٔ غربالگری (خام از API)"]
urlLink: https://example.com/a1 | back: true | alerts: 0
failures: []
```

Also asserted: the retryable task shows its sanitized error (`timeout`) with the Persian status label
«قابل تلاش مجدد», the cluster section lists only the sibling (`a2`, not itself), clicking it
navigates to `#/news/article-a2`, and the page renders no error banner while data is served.

The first run failed one check because the panel title was still «جزئیات خبر» while the assertion
expected «جزئیات مقاله»; the title was made explicit in the UI (not the assertion relaxed).

## 5. Known gaps

| Severity | Gap |
|---|---|
| `MEDIUM` | `/api/dedup/clusters` returns every article, so the cluster check is a full-list fetch; a filtered endpoint is needed before large datasets |
| `MEDIUM` | Priority reason codes are not exposed for a single article; the UI states this instead of showing reasons |
| `LOW` | Dispatch read model has no timestamps, so the processing list is state-based, not chronological |
| `LOW` | No visual-regression baseline for the detail layout |

**Next stage:** `F03.UX.6` — responsive/RTL/keyboard sweep at 360/768/1024, or `F03.0` backend
control plane (descriptor, revisions, validate/test/preview, audit).
