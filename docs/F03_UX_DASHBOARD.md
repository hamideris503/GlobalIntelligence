# F03.UX.3 — Dashboard as a decision surface

**Stage:** `F03.UX.3`
**Status:** `VERIFIED` for the KPI contract, states, deep links and the global-error behaviour;
`PARTIALLY_VERIFIED` overall because there is no visual-regression harness and the signed-out path
was verified through request interception, not against a live authenticated backend.
**Scope:** dashboard KPIs with definitions/source/freshness, an "action required" list, KPI → filtered
list links, and one page-level banner instead of repeated per-panel errors. No API/DB/migration
change, no new dependency.

---

## 1. Before (evidence)

From `docs/UI_UX_AUDIT.md` §5 and `UX-03`/`UX-19`/`UX-02`:

- KPI values came from real APIs but had **no definition, no source path and no `last_updated_at`**.
- "پیش‌بینی‌های ثبت‌شده" counted `GET /api/forecasts?limit=200` and presented a page of results as a
  total.
- No KPI linked to the filtered dataset behind it.
- A missing key produced up to **8 identical error panels** (measured: `role=alert` = 8).

## 2. After — KPI contract

Every KPI renders: label, value, status badge (`تازه` / `کهنه` / `بدون مهر زمانی` / `نامشخص`),
`as of` line, a `<details>` block with the definition **and the exact source path**, and a link.

| KPI | Source (shown in UI) | Freshness source | Link |
|---|---|---|---|
| اخبار دریافت‌شده | `GET /api/ops/status → counts.articles` | newest `retrieved_at` of loaded articles | `#/news` |
| رویدادهای شناسایی‌شده | `GET /api/ops/status → counts.events` | none in API → `بدون مهر زمانی` | `#/news/events` |
| منابع فعال | `GET /api/sources → active` | **oldest** successful `last_success` of active sources | `#/sources` |
| منابع دارای خطا | `GET /api/sources → last_error` | same (worst case) | `#/sources/error` |
| هشدارهای فعال | `GET /api/ops/status → active_alerts` | none in API → `بدون مهر زمانی` | `#/ops` |
| اجراهای ناموفق | `GET /api/ops/status → last_jobs[].status` | none → `بدون مهر زمانی`, footnote states it is only the `last_jobs` window | `#/ops` |

Rules encoded:

- Backend `-1`/null → **`نامشخص`**, never `0`.
- Freshness uses the **oldest** timestamp for source health, so one stale source cannot be hidden by
  a fresh one (this was a real defect found by the verification, not by review).
- Missing timestamp is an explicit third state, never rendered as success/`تازه`.
- `P0–P4` counts were deliberately **not** invented on this page: the dashboard API exposes no
  priority aggregate, and mapping `importance` (1–10) to P-levels is a domain decision.

## 3. "نیازمند اقدام" (action required)

Renders only non-zero, actionable items with counts and a direct route: sources with errors →
`#/sources/error`, failed runs → `#/ops`, active alerts → `#/ops`. When nothing is actionable it says
so explicitly instead of showing empty cards.

## 4. Deep links (new behaviour)

- `#/news/events` opens the events tab (`pages/news.tsx` reads the route param).
- `#/sources/error` opens the sources list with a new **`فقط دارای خطا`** filter pre-checked
  (`pages/sources.tsx` + `App.tsx` passes `route.param`).
- Both are hash routes, so refresh/back work.

## 5. Global error handling (UX-02, partial)

The dashboard now classifies the first global failure into **auth** (`کلید API`) or **offline**
(`ارتباط با سرور`) and renders **one** banner with the matching action; the per-widget `error` prop is
suppressed while that banner is active, and each panel shows a single explanatory empty state.

## 6. Verification

```bash
cd apps/web && npm run typecheck          # exit 0
cd apps/web && npm run build              # exit 0, JS 336.36 kB (107.37 kB gzip)
npm run preview -- --port 4173 --strictPort
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-dashboard.mjs   # exit 0
```

Deterministic **test-only** fixtures are injected through Playwright request interception (the app
ships no mock data). Measured result:

```
اخبار دریافت‌شده      | ۱۲ خبر | تازه            | GET /api/ops/status → counts.articles
رویدادهای شناسایی‌شده  | ۴ رویداد | بدون مهر زمانی | GET /api/ops/status → counts.events
منابع فعال           | ۲ از ۲ | کهنه           | GET /api/sources → active
منابع دارای خطا       | ۱ منبع | کهنه           | GET /api/sources → last_error
هشدارهای فعال         | ۲ هشدار | بدون مهر زمانی | GET /api/ops/status → active_alerts
اجراهای ناموفق        | ۱ اجرا | بدون مهر زمانی  | GET /api/ops/status → last_jobs[].status
actions: 3 | #/sources/error with "فقط دارای خطا" checked | #/news/events opens رویدادها
signed-out: role=alert = 1, .errbox = 0, banner = "ارتباط با سرور برقرار نشد…"
failures: []
```

The first run of this script failed 3 checks — the stale-source badge, and the duplicated error blocks
when the failure was a CORS/offline error rather than a 401. Both were fixed in the code above, not in
the assertions.

## 7. Known gaps

| Severity | Gap |
|---|---|
| `MEDIUM` | Other pages still repeat per-widget error blocks; the shared state contract belongs to UX.5 |
| `MEDIUM` | No priority (`P0/P1`) aggregate exists in the API, so the dashboard cannot show it without a domain/backend decision |
| `LOW` | Freshness for events/alerts/failed runs is `بدون مهر زمانی` because the API returns no timestamp — an API gap, deliberately not faked |
| `LOW` | No visual regression baseline for the new KPI grid |

**Next stage:** `F03.UX.4` — inbox/workflow detail (priority reason codes, provenance, duplicate
cluster) or `F03.UX.5` — unified loading/empty/error/stale states across pages.
