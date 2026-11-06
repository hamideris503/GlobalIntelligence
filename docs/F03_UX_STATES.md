# F03.UX.5 — Unified loading / empty / error / stale states

**Stage:** `F03.UX.5`
**Status:** `VERIFIED` for the global-error contract, empty and no-results states across the five
primary routes; `PARTIALLY_VERIFIED` overall (no visual-regression harness, no screen-reader pass,
stale/offline timestamp strip not implemented on every page).
**Scope:** one shared state contract for API failures and empty results. No API/DB/migration change,
no dependency added, no page functionality removed.

---

## 1. Before (evidence)

From `docs/UI_UX_AUDIT.md` §7 and `UX-02`, measured on the pre-change build:

- A single global failure (missing key, server down, CORS) produced **up to 8 identical error panels**
  on the dashboard and duplicated panels on other pages (`role=alert` = 8, `.errbox` = 8).
- Every page re-implemented loading/empty handling locally; `Empty` was a bare text box with no next
  action, and a filtered list that matched nothing looked identical to "no data at all".
- No correlation id existed, so an error could not be referenced in a report.

## 2. Shared contract (implemented)

| Kind | Trigger | UI |
|---|---|---|
| `auth` | 401 from any request | one banner; "تنظیم کلید" + "تلاش مجدد"; persists until the key changes |
| `permission` | 403 | one banner, no settings shortcut |
| `server` | any 5xx | one banner with retry; cleared automatically on the next success |
| `offline` | network `TypeError` / timeout (`AbortError`) | one banner with retry |
| local (4xx other) | 422/409/404 etc. | stays in its own panel via `Err` (not globalised) |

Implementation in `apps/web/src/ui.tsx`:

- `classifyApiError()` → `GlobalIssueKind | null`; `reportApiError()` writes a module-level store with
  a short `ref` (`kind-<base36 time>`) that contains no sensitive data; `reportApiSuccess()` clears
  transient issues but keeps `auth`.
- `useGlobalIssue()` subscribes components to the store (no synchronous `setState` inside the effect).
- `GlobalNotice` renders **once** in `Shell`; `Section` and `Err` suppress their own error output while
  a global issue is active, so no page needs to be rewritten to benefit.
- `retry()` in `KeyProvider` bumps the shared version that every `useApi` includes in its deps, so the
  retry button re-runs all mounted requests instead of only the clicked panel.
- `Empty` gained an optional `action`; `NoResults` is a new primitive with a "پاک کردن فیلترها" action.

## 3. Pages wired in this stage

| Page | Change |
|---|---|
| `news` | filtered-but-empty now shows `NoResults` with a real clear action (query, topic, importance) |
| `sources` | filtered-empty → `NoResults`; truly-empty → `Empty` with "افزودن اولین منبع" |
| `dashboard` | local auth/offline banner removed; relies on the shared banner (no duplicate message) |
| all routes with `Section`/`Err` | per-panel duplicates suppressed automatically |

## 4. Verification

```bash
cd apps/web && npm run typecheck                       # exit 0
cd apps/web && npx eslint src/ui.tsx src/pages/dashboard.tsx src/pages/news.tsx src/pages/sources.tsx
                                                       # 0 errors, 7 react-refresh warnings
cd apps/web && npm run build                           # exit 0, JS 338.10 kB (107.88 kB gzip)
npm run preview -- --port 4173 --strictPort
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-states.mjs   # exit 0
```

Measured result (5 routes × 3 failure kinds, test-only interception):

```
auth    | pages: 5 | banners/page: 1.00 | errbox: 0 | max alerts: 1
server  | pages: 5 | banners/page: 1.00 | errbox: 0 | max alerts: 1
offline | pages: 5 | banners/page: 1.00 | errbox: 0 | max alerts: 1
failures: []
```

Additional assertions from the same run: the banner text matches the failure kind, a retry button and
a copyable `ref` are present, the no-results state appears for a non-matching query and clearing it
restores the row and empties the input, and the empty source list offers "افزودن اولین منبع".

## 5. Deviations and fixes during the stage

- The first attempt produced a JSX syntax error in `news.tsx` (a brace inside a ternary branch) and
  `eslint` rejected a synchronous `setState` inside an effect in `useGlobalIssue`. Both were fixed in
  the code; no rule or assertion was relaxed.
- `dashboard` briefly had two banners (its own + the shared one) until its local banner was removed.

## 6. Known gaps

| Severity | Gap |
|---|---|
| `MEDIUM` | A per-page "last synced at" strip (stale/degraded timestamps) is only implemented on the dashboard and on pages that already had a freshness line; not yet universal |
| `MEDIUM` | Partial-success reporting (`n موفق / m ناموفق`) exists only for `RunButton` inline results |
| `LOW` | No screenshot-based regression baseline for these states |
| `LOW` | `permission` (403) has no dedicated test route in the app to exercise end-to-end |

**Next stage:** `F03.UX.4` — inbox/detail workflows (priority reason codes, provenance, duplicate
cluster, job timeline) or `F03.UX.6` — responsive/RTL/keyboard sweep at 360/768/1024.
