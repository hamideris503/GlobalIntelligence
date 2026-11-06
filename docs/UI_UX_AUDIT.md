# UI/UX Audit — F03.UX.0 (read-only baseline)

**Stage:** 1 — `F03.UX.0` UI/UX audit
**Status:** `PARTIALLY_VERIFIED` — inventory, navigation map, task-flow traces, viewport and
accessibility observations are complete and evidence-backed; the two criteria that need
credentials/human testers are recorded as limitations (§9), not as passes.
**Read-only:** no application file was changed. The only files added by this stage are this
document, `docs/DELTA_IMPLEMENTATION_INVENTORY.md` and the baseline artifacts in
`docs/audit-baseline/`.

**Environment:** Windows 11, local dev servers already running — Vite `http://localhost:5173`,
FastAPI `http://localhost:8000` (`GET /health` → `{"status":"ok"}`, `MOCK_MODE=true`).
Capture script: `docs/audit-baseline/capture.mjs` (Playwright, read-only, re-runnable:
`node docs/audit-baseline/capture.mjs`).

---

## 1. Route inventory

27 route names in `apps/web/src/router.ts` (`parseHash`), all mapped 1:1 in
`apps/web/src/App.tsx`. One shared layout: `Shell` (`apps/web/src/ui.tsx`) = sidebar + topbar +
`<main>`; every route is a child of it. Authorization for every data call is the same
`X-API-Key` header injected in `apps/web/src/api.ts`; there is no per-route permission model in
the frontend, and the backend enforces it (all routers are registered behind `protected` in
`backend/main.py`).

| Route ID | Page (file) | Nav group / label | Primary APIs | loading / error / empty |
|---|---|---|---|---|
| `dashboard` | `pages/dashboard.tsx` | نمای کلی / داشبورد | `/api/ops/status`, `/api/sources`, `/api/classify/articles`, `/api/forecasts`, `/api/world-state/current`, `/api/risk/overview`, `/api/markets/latest` + `/observations`, `/api/briefings` | loading ✓, error per panel ✓, empty ✓, stale ✗ |
| `news` | `pages/news.tsx` (+`article-<id>`, `event-<id>`) | نمای کلی / اخبار و رویدادها | `/api/classify/articles`, `/api/classify/articles/{id}`, `/api/events`, `/api/claims` | ✓ / ✓ / ✓ |
| `sources` | `pages/sources.tsx` | داده و هوش مصنوعی / منابع اطلاعاتی | `/api/sources`, `PATCH /api/sources/{id}`, `/api/sources/{id}/recheck`, `/api/ingest`, `/api/ingest/all`, `/api/sources/export/all` | ✓ / ✓ / ✓ |
| `ai` | `pages/ai.tsx` | داده و هوش مصنوعی / هوش مصنوعی و مدل‌ها | `/api/ai/providers`, `/api/ai/status`, `/api/ai-routing/routes`, `/api/ai-routing/apply`, `/api/ai/generate` | ✓ / ✓ / ✓ |
| `chat` | `pages/chat.tsx` | داده و هوش مصنوعی / گفت‌وگو | `/api/ai/chat`, `/api/settings/models`, `/api/settings/providers` | ✓ / ✓ / n/a |
| `connections` | `pages/connections.tsx` | داده و هوش مصنوعی / اتصالات و APIها | `/health`, `/api/ai/providers`, `/api/sources` | ✓ / ✓ / ✓ |
| `keys` | `pages/keys.tsx` | داده و هوش مصنوعی / کلیدها و سرویس‌ها | `/api/ai/providers`, `/api/ai/status` | ✓ / ✓ / ✓ |
| `world` | `pages/world.tsx` | تحلیل جهان / وضعیت جهان | `/api/world-state/{current,history,build}`, `/api/economic/{fetch,indicators,latest}`, `/api/macro/{analyze,overview}` | ✓ / ✓ / ✓ |
| `macro` | same file | تحلیل جهان / اقتصاد کلان | as above | ✓ / ✓ / ✓ |
| `geo` | `pages/geo.tsx` | تحلیل جهان / ژئوپلیتیک و سیاست | `/api/geopolitics/{tensions,analyze}`, `/api/society/{mood,analyze}` | ✓ / ✓ / ✓ |
| `society` | `pages/society.tsx` | تحلیل جهان / هوشمندی اجتماعی (`dev` badge) | none (placeholder) | n/a — explicit "in development" state |
| `iran` | `pages/geo.tsx` | تحلیل جهان / ایران | `/api/iran/{brief,transmission,transmission/analyze}` | ✓ / ✓ / ✓ |
| `markets` | `pages/markets.tsx` | بازار و تصمیم / بازارهای مالی | `/api/markets/{symbols,latest,observations,fetch}` | ✓ / ✓ / ✓ |
| `forecast` | `pages/analysis.tsx` | بازار و تصمیم / پیش‌بینی‌ها | `/api/forecasts`, `/api/forecasts/ledger/active`, `/api/forecasts/run` | ✓ / ✓ / ✓ |
| `debate` | `pages/debate.tsx` | بازار و تصمیم / بحث مدل‌ها | `/api/debate/runs`, `/api/debate/runs/{id}`, `/api/decisions/from-debate` | ✓ / ✓ / ✓ |
| `scenarios` | `pages/analysis.tsx` | بازار و تصمیم / سناریوها و ریسک | `/api/scenarios`, `/api/scenarios/run`, `/api/risk/overview`, `/api/risk/analyze` | ✓ / ✓ / ✓ |
| `decisions` | `pages/analysis.tsx` | بازار و تصمیم / تصمیم‌ها و پیشنهادها | `/api/decisions`, `/api/decisions/run`, `/api/audit/log` | ✓ / ✓ / ✓ |
| `portfolio` | `pages/portfolio.tsx` | بازار و تصمیم / سبد دارایی | `/api/portfolios`, `/api/portfolios/{id}/snapshot(s)` | ✓ / ✓ / ✓ |
| `evaluation` | `pages/portfolio.tsx` | بازار و تصمیم / ارزیابی عملکرد | `/api/evaluation/*`, `/api/self-eval/*`, `/api/debate/scorecard` | ✓ / ✓ / ✓ |
| `history` | `pages/misc.tsx` | سیستم / تاریخچه و گزارش‌ها | `/api/briefings`, `/api/briefings/{id}`, `/api/briefings/{daily,weekly}` | ✓ / ✓ / ✓ |
| `ops` | `pages/misc.tsx` | سیستم / پردازش‌ها و وظایف | `/api/jobs`, `/api/ops/monitoring`, `/api/alerts` | ✓ / ✓ / ✓ |
| `screening` | `pages/screening.tsx` | سیستم / غربالگری و صف پردازش | `/api/screening/queue`, `/api/screening/review/{id}/ack`, `/api/dispatch/jobs`, `/api/dispatch/{id}/retry`, `/api/local-runtimes/status` | ✓ / ✓ / ✓ |
| `settings` | `pages/settings.tsx` | سیستم / **Settings** | `/api/settings/{app,models,providers,diversity,agent-assignments,import-from-env}` + model verify/block | ✓ / ✓ / partial |
| `archive` | `pages/archive.tsx` | سیستم / **Archive** | `/api/archive/{catalog,settings,storage,validate,restore/dry-run,purge/preview}` | ✓ / ✓ / ✓ |
| `help` | `pages/misc.tsx` | سیستم / راهنما | static | n/a |
| `search` | `pages/misc.tsx` | not in nav (topbar search) | `/api/classify/articles`, `/api/events`, `/api/sources`, `/api/briefings` | ✓ / ✓ / ✓ |

Route-level findings:

- `parseHash()` returns `dashboard` for any unknown route — a mistyped bookmark silently lands
  on the dashboard with no explanation (`UX-09`).
- Detail routes are sub-parameters of `news` only (`article-<id>`, `event-<id>`); no other
  entity is deep-linkable (no `#/sources/<id>`, `#/ops/<job>`).
- Filters/sort/search of every list page live in component state; a reload or browser Back
  loses them (`UX-08`).

---

## 2. Component inventory

| Component | Defined in | Consumers | Duplicate / competing pattern |
|---|---|---|---|
| `Shell`, `KeyProvider`, `ToastProvider` | `ui.tsx` | `App.tsx` | — |
| `useApi` | `ui.tsx` | 20 pages | `components/ui/conversation.tsx` has its own fetch/state path |
| `Table` (sortable, client-side) | `ui.tsx` | `news`, `sources`, `screening`, `misc`, `markets`… | `screening.tsx` builds its own rows/pagination markup |
| `Modal`, `ConfirmDialog`, `Field` | `ui.tsx` | `sources`, `settings`, `news`, `analysis` | `settings.tsx` renders its own overlay/dialog blocks |
| `Section` (panel + loading + error) | `ui.tsx` | 18 pages | pages also use bare `.panel` + `.page-head` markup (`news`, `sources`, `settings`) |
| `PageHeader` | `ui.tsx` | few | `.page-head` markup duplicated inline in ≥8 pages |
| `StatCard` | `ui.tsx` | dashboard, markets | metrics in `misc.tsx` are plain `<dl>` |
| `Badge` (`ok/warn/bad/info/demo`) | `ui.tsx` | many | priority is rendered as raw text/number, no P0–P4 scale anywhere |
| `Empty`, `Err`, `Spinner` (skeleton), `StateBanner`, `MockTag` | `ui.tsx` | many | `settings.tsx`/`archive.tsx` hand-roll "loading" and "error" text |
| `LineChart`, `Bars`, `Donut`, `Sparkline` | `ui.tsx` | dashboard, markets, analysis | — |
| `Button` (CVA + Tailwind) | `components/ui/button.tsx` | chat components only | **second, unrelated button system** vs the global `button` element styles |
| `Loader`, `Response`, `Markdown`, `Conversation` | `components/ui/*` | chat page | Tailwind utilities vs global CSS |
| Icons | `icons.tsx` (40 icons, inline SVG) | all pages | one system, `IconName` typed but call sites pass `string` |

Conclusion: the design system is **partial** — primitives exist but there are two styling
regimes (global CSS + Tailwind utilities), two button systems, three error/loading idioms and no
documented component contract.

---

## 3. Navigation map

Current (5 groups, 25 items, `NAV_GROUPS`):

```
نمای کلی        داشبورد · اخبار و رویدادها
داده و هوش مصنوعی  منابع اطلاعاتی · هوش مصنوعی و مدل‌ها · گفت‌وگو · اتصالات و APIها · کلیدها و سرویس‌ها
تحلیل جهان      وضعیت جهان · اقتصاد کلان · ژئوپلیتیک و سیاست · هوشمندی اجتماعی(توسعه) · ایران
بازار و تصمیم   بازارهای مالی · پیش‌بینی‌ها · بحث مدل‌ها · سناریوها و ریسک · تصمیم‌ها · سبد دارایی · ارزیابی
سیستم          تاریخچه و گزارش‌ها · پردازش‌ها و وظایف · غربالگری و صف پردازش · Settings · Archive · راهنما
```

Problems:

1. **Mixing of concerns.** Ingestion lives in three places (`sources`, `screening`, quick
   actions on the dashboard) and operations in two (`ops`, `screening`); "منابع اطلاعاتی" is
   filed under "داده و هوش مصنوعی", not ingestion.
2. **Untranslated/system labels** inside a Persian menu: `Settings`, `Archive` (`UX-05`).
3. **Two items share one icon** (`screening` and `ops` both use `ops`; `archive` too) — no way
   to distinguish them at a glance.
4. **No badge for real state.** Only static "توسعه"/"نیازمند اتصال" badges exist; a page whose
   backend is failing, or the number of items needing action, is not visible from the menu.
5. **Global search is unreachable on mobile** — `.searchbox` is `display:none` under 960px and
   nothing replaces it (`UX-07`).
6. Deep links are not reflected in nav (search page has no nav entry), and there is no
   breadcrumb anywhere.

Proposed grouping (task-based, keeps route names): Overview · Intelligence (inbox, clusters,
search) · Analysis · Ingestion (sources, runs, screening) · Operations (jobs, alerts, audit) ·
Integrations (providers, Telegram) · Archive · Settings — with `Settings`/`Archive` translated
and one distinct icon per item.

---

## 4. Workflow map (traced through code + observed in signed-out state)

| # | Flow | Actual steps today | Stop / error points |
|---|---|---|---|
| 1 | Understand what needs action | dashboard → scan 6 stat cards → scan 8 panels | 8 panels ask for the API key separately; one auth failure produces 8 identical error blocks and no single "fix this first" (`UX-02`) |
| 2 | Find an important article, see why | `#/news` → type in free-text filter → sort column → open detail | priority shown as a raw number; no P0–P4 vocabulary, no reason codes, no duplicate-cluster link (`UX-04`, `UX-11`) |
| 3 | Inspect a duplicate cluster | not reachable from the inbox; `dedup` has only `POST /api/dedup/run` in the UI | feature gap, no route (`UX-12`) |
| 4 | Add and test a source | `#/sources` → "افزودن منبع" modal → 7 fields + feed URL → save (row is active immediately) | no adapter-driven fields, no validate/test/preview, "دریافت آزمایشی" performs a real ingest (`UX-01`) |
| 5 | Configure a provider | `#/ai` / `keys` / `settings` (three entry points) → add credential → verify → enable | three competing surfaces for one job; state vocabulary differs per page (`UX-06`) |
| 6 | Diagnose a failed job | `#/ops` list → job row | no timeline, no attempt/checkpoint/config-revision, retry only exists for dispatch items (`UX-13`) |
| 7 | Manage an alert | `#/ops` → alerts tab → ack | no priority grouping, no resolve/delivery state, no link to the triggering entity (`UX-13`) |
| 8 | Check archive & recovery | `#/archive` → catalog → validate → dry-run restore → purge preview | states are separate panels but upload/verify/restore/purge share one visual weight; purge gate is preserved (positive) |

Step counts above are **code-traced**, not measured with a user; no time/click claim is made.

---

## 5. Data-integrity map (KPI sources)

| KPI / widget | Source | Real? | Freshness shown? | Failure behaviour |
|---|---|---|---|---|
| اخبار دریافت‌شده / رویدادها | `/api/ops/status.counts` | real | ✗ | whole panel replaced by error |
| منابع فعال / دارای خطا | `/api/sources` | real | partial (`last_success` inside a chip) | `نامشخص` |
| پیش‌بینی‌های ثبت‌شده | `/api/forecasts?limit=200` | real but **count of the first 200 rows** — labelled "حداقل ۲۰۰ (سقف دریافت)" | ✗ | `نامشخص` |
| دیتابیس | `/api/ops/status.database_ok` | real | ✗ | red |
| روند بازار | `/api/markets/latest` + `/observations` | real | ⚠ only the first symbol | empty state |
| توزیع موضوعی | `/api/classify/articles?limit=200` client aggregation | real, truncated to 200 | ✗ | empty state |
| هشدارهای ریسک | `/api/risk/overview` | real | ✗ | empty state |
| آخرین فعالیت‌ها | `/api/ops/status.last_jobs` | real | ✗ | empty state |

No fabricated numbers were found. Dashboard does not display `last_updated_at` for any KPI and
no KPI links to its filtered dataset (`UX-03`). `MockTag` correctly labels mock classifications.
`forecasts` uses `limit` as a count — a cardinality metric masquerading as a total.

---

## 6. Responsive audit

Measured with `capture.mjs` at 1440×900, 768×1024, 390×844 over 7 routes
(`docs/audit-baseline/baseline.json`, 21 screenshots).

| Finding | Evidence |
|---|---|
| No document-level horizontal overflow on any sampled route at any viewport (`scrollWidth == innerWidth`) | baseline.json, all 21 rows |
| Sidebar collapses to an off-canvas drawer < 860px; identity and search disappear | `04-sources-390.png` — only icons remain in the topbar |
| Status pills lose their text < 860px and become **colour dots only** | `04-sources-390.png` vs `01-dashboard-1440.png` (`UX-14`) |
| Mobile topbar exposes 6–7 icon targets with no labels; global search has no mobile entry point | `UX-07` |
| Settings tab strip overflows its container and clips the last tab; the page subtitle is clipped | `05-settings-1440.png` |
| Skeleton block overlaps its own caption text in "بازنگری" | `05-settings-1440.png` |
| Sources footer hint sits under the last panel, partially clipped | `04-sources-390.png` |
| Wide tables scroll inside `.tablewrap` with no affordance that more columns exist | `02-news-1440.png`, `pages/news.tsx` |
| Detail pages on mobile use `.kv` (150px label column) which squeezes values at 390px | `styles.css` `.kv` + 860px override to 110px |

---

## 7. Accessibility audit

| Check | Result |
|---|---|
| `html[dir="rtl"]`, Persian-first UI | ✓ (`index.html`) |
| Landmarks | ✓ `aside[aria-label]`, `header`, `main`, `nav` |
| One `<h1>` per page | ✓ measured `headingCount = 1` on all 7 sampled routes |
| Table headers sortable via `<button>` with `aria-label` | ✓ |
| Focus ring | ✓ global `:focus-visible { outline: 2px solid var(--brand) }` |
| Icon-only buttons | ✓ all carry `aria-label` |
| Touch target size | ✓ measured 0 targets under 32px on all sampled routes |
| **Meaning conveyed by colour alone** | ✗ status pills at <860px are dots without text; `Badge` tone conveys state with no text difference in several call sites (`UX-14`) |
| **Focus management on route change** | ✗ `<main key>` remounts; focus stays on the sidebar button, no announcement (`UX-10`) |
| **Focus trap / focus return in Modal and mobile drawer** | ✗ `Modal` closes on Escape but never traps or restores focus; drawer has no focus handling (`UX-10`) |
| **`aria-describedby` for field help/error** | ✗ `Field` renders `<small>` inside the label with no id wiring (`UX-15`) |
| Status announcements for async results | partial — toasts use `role="status"`, but `RunButton` results are plain spans |
| Reduced motion | ✓ `@media (prefers-reduced-motion: reduce)` disables animation/transition |
| Contrast | **not measured** — no automated contrast run in this stage; visually, `--muted` on `--bg` at 0.84rem is the first suspect (`#7e8ca0` on `#0a0e14`) |
| Screen reader walk-through | `NOT RUN` — no screen reader available in this environment |

---

## 8. Performance baseline (what was actually measured)

Only first-navigation settle time to `networkidle` + one interaction-free render was measured;
this is **not** Core Web Vitals and no LCP/CLS/INP claim is made.

| Observation | Value |
|---|---|
| Route settle (1440) | dashboard 2039 ms; news 701 ms; sources 699 ms; ai 683 ms; settings 686 ms; ops 681 ms; archive 729 ms |
| Route settle (390) | dashboard 10347 ms (dominated by waiting for 401 retries ×8 endpoints); other routes 649–667 ms |
| Bundle | single entry, no route-level code splitting (`App.tsx` imports all 27 pages) |
| Duplicate requests | dashboard requests 9 endpoints on mount and again on every `refresh()`; no caching layer |
| Layout shift | not measured (no CLS instrumentation); skeleton blocks have fixed heights inside panels, so no obvious jump observed |

Absolute numbers are machine-specific (Windows, dev server, unminified bundle) and must not be
compared with production.

---

## 9. Limitations of this audit

1. **Signed-out baseline only.** No API key was available to this read-only stage, so every
   authenticated route renders its `401` state. Screenshots therefore document layout, typography,
   navigation and error states, **not** populated tables/charts. No mock data was substituted for
   real data (per spec).
2. **No human usability test.** Flows in §4 are code-traced; no task time, click count or success
   rate is claimed.
3. **No screen reader, no axe, no Lighthouse.** Contrast and CWV are unmeasured and not claimed.
4. **No production-parity database** for dashboard values; counts come from the local DB state.

---

## 10. Prioritized backlog

Severity: `BLOCKER` = task impossible / misleading data / unsafe; `HIGH` = frequent task impaired;
`MEDIUM` = friction or inconsistency; `LOW` = polish. Frequency = how often the surface is used.

| ID | Severity | Problem (evidence) | Impact | Proposed fix | Depends on |
|---|---|---|---|---|---|
| `UX-01` | **BLOCKER** | "دریافت آزمایشی" on a source calls `POST /api/ingest` — a preview that silently ingests (`pages/sources.tsx`) | data pollution, breaks the "preview never ingests" rule | non-destructive preview path + explicit "not ingested" labelling | F03.0 + adapter `preview()` |
| `UX-02` | **BLOCKER** | one missing key produces up to 8 identical error panels (`01-dashboard-1440.png`, 8 `role=alert`) | user cannot tell what is broken; page looks unusable | single page-level auth/health banner, per-widget disabled state with local retry | UX.5 |
| `UX-03` | HIGH | dashboard KPIs have no definition, no `last_updated_at`, no link to filtered data | decisions made on unlabelled/possibly stale numbers | KPI metadata block + deep links + stale labels | UX.3, backend timestamps |
| `UX-04` | HIGH | priority/importance is a raw number with inverted scale and an explanatory paragraph; no P0–P4 vocabulary, no reason codes | the core "why is this important" question is unanswerable | shared priority token + badge with text, reason-code panel in detail | UX.1, UX.4 |
| `UX-05` | HIGH | navigation mixes domains; `Settings`/`Archive` untranslated; two items share an icon | discovery cost on every session | regroup per §3, translate, unique icons | UX.2 |
| `UX-06` | HIGH | provider configuration spread over `ai`, `keys`, `settings`, `connections` with different state vocabularies | user cannot tell where the real control is | one provider surface on the shared control plane; the others link to it | F03.0 |
| `UX-07` | HIGH | global search unreachable on mobile (<960px hidden, no replacement) | mobile users have no search | mobile search entry (icon → full-width field or palette) | UX.2 |
| `UX-08` | HIGH | list filters/sort/page live only in component state | Back/reload loses work; no shareable links | persist to hash query + chips + clear-all | UX.4 |
| `UX-09` | MEDIUM | unknown hash silently renders dashboard | user believes link worked | explicit 404 route with recover action | UX.2 |
| `UX-10` | HIGH | no focus move on route change; Modal does not trap/restore focus; drawer leaves focus behind the scrim | keyboard users lost; WCAG 2.4.3/2.1.2 risk | focus manager in Shell + dialog/drawer focus trap | UX.1 |
| `UX-11` | HIGH | article detail lacks provenance timeline, priority reason, duplicate cluster link | provenance requirement not met at the decision point | restructure detail per spec §10.8 | UX.4 |
| `UX-12` | MEDIUM | duplicate clusters have no UI at all (`dedup` run only) | duplicate triage impossible | cluster list + canonical link inside inbox | UX.4 |
| `UX-13` | HIGH | Jobs/Alerts show no timeline, attempt, checkpoint, config revision or sanitized error detail | failed job cannot be diagnosed | job detail drawer with safe timeline | UX.4, F03.0 revisions |
| `UX-14` | HIGH | status meaning by colour only at <860px; badges rely on tone | colour-blind users lose state; WCAG 1.4.1 | always show status text; dots get `aria-label` + tooltip text | UX.1 |
| `UX-15` | MEDIUM | `Field` does not wire `aria-describedby`/`aria-invalid`; validation errors not summarized | screen-reader users miss errors | FormField contract + error summary | UX.1 |
| `UX-16` | **BLOCKER (cosmetic but global)** | `font-family` resolves to `Times New Roman` everywhere — self-referential `--font-sans` in `tw.css` | every screen's Persian typography is wrong | remove the self-reference; verify computed `font-family` on all routes | none |
| `UX-17` | MEDIUM | Settings tabs overflow and clip; skeleton overlaps caption | looks broken; last tab unreachable | scrollable tab strip + non-overlapping skeleton | UX.1 |
| `UX-18` | MEDIUM | two styling regimes (global CSS + Tailwind utilities) and two Button systems | every future component forks again | one contract; Tailwind bridge only for chat components | UX.1 |
| `UX-19` | MEDIUM | metrics computed from a truncated `limit=200` list are presented as totals | misleading counts | server-side aggregate endpoint or explicit "of first N" label | UX.3 |
| `UX-20` | LOW | duplicate brand text in topbar and sidebar; search box placeholder key hint only | noise | single brand anchor, keyboard hint chip | UX.2 |
| `UX-21` | LOW | no component/visual/a11y test harness; E2E covers 3 flows | regressions invisible | vitest + Playwright visual + axe (needs dependency approval) | gate |

---

## 11. Exit criteria for F03.UX.0

| Criterion | Result |
|---|---|
| All routes and main layouts inventoried | ✓ 27 routes, one shared shell, API + state per route |
| Screenshot/baseline for key pages, or documented limitation | ✓ 21 screenshots at 3 viewports; limitation = signed-out state only (§9) |
| Task flows and ranked issues with evidence | ✓ 8 flows traced, 21 ranked issues with file/screenshot evidence |
| Current stack and compatible options known | ✓ §1 of the inventory doc; no new framework needed |
| Nothing changed without reason; audit truly read-only | ✓ only docs + baseline evidence added |

Recommended next stage (requires the owner gate): **F03.UX.1 — design tokens and shared
components**, starting with `UX-16`, the token contract (status/P0–P4/focus/motion) and the
component contract for Button/Field/Dialog/DataTable/Empty/Error.
