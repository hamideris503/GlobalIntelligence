# F03.UX.6 — Responsive / RTL / keyboard

**Stage:** `F03.UX.6`
**Status:** `VERIFIED` — 21 route×viewport combinations (7 routes × 360/768/1024) measured in a
browser against the production build: **0 layout issues**, no horizontal document overflow, no
squeezed key-value values, `dir=rtl` everywhere, and the UX.2 keyboard checks still pass.
**Scope:** layout/CSS and two component fixes. No API, DB, migration or dependency change.

---

## 1. Before (measured, not assumed)

`verify-responsive.mjs` on the pre-stage build:

```
issues: 7
 - 360/dashboard: document overflow   - 360/news: document overflow
 - 360/sources: document overflow     - 360/screening: document overflow
 - 360/settings: document overflow    - 360/ops: document overflow
 - 360/archive: document overflow
```

Every route scrolled horizontally at 360px. `diag-overflow.mjs` refused to accept the symptom and
located the cause in three steps:

1. `documentElement.scrollWidth = 412` at **both** 360 and 390 → a fixed-width contributor, not a
   percentage one.
2. Offender scan: `aside.sidebar` (fixed drawer) reached `right: 660`, and `.skip-link` sat at
   `right: 10359` — the RTL `inset-inline-start: -9999px` trick pushes the element to the *right*
   edge in RTL, growing the document.
3. After containing the drawer, `topbar scrollWidth 412 / clientWidth 360` with all children inside
   the viewport, and the two last `.iconbtn`s sitting at negative `left` (RTL inline-end).

Root cause of the topbar width: the `@media (max-width: 860px)` block that shows `.topbar-title`
appears **later** in `styles.css` than the new `≤520px` block that hides it, so at equal specificity
the later rule won and the 150px wordmark stayed visible on a 360px bar.

## 2. Fixes

| File | Change |
|---|---|
| `styles.css` | `.kv` columns `minmax(88px,132px) minmax(0,1fr)`; at `≤520px` the pair stacks label-over-value so long URLs are not squeezed |
| `styles.css` | `.tablewrap` keeps `overflow-x:auto`, gains a thin scrollbar; `.tablehint` appears at `≤860px` |
| `styles.css` | `.skip-link` hidden by **vertical** offset (`top: -64px`, `position: fixed`) instead of a negative logical inset — no document growth in either direction |
| `styles.css` | Mobile drawer closed state uses `visibility/opacity/pointer-events` instead of `translateX(100%)`, so the off-canvas panel no longer adds width; `.open` switches `visibility` immediately and delays it on close (`transition: opacity .18s, visibility 0s linear .18s`) so focus lands inside the panel |
| `styles.css` | `≤520px` block: tighter topbar gap/padding, 34px icon buttons, smaller status pills, stacked global notice, and `.topbar .topbar-title{display:none}` with the extra specificity the cascade requires |
| `ui.tsx` | `Table` renders its scroll container as `role="region"`, `tabIndex={0}`, `aria-label="جدول قابل پیمایش افقی"` + a visible `.tablehint` |
| `settings.tsx` | Settings tabs migrated from ad-hoc buttons to the shared `Tabs` component (arrow-key/Home/End navigation, roving `tabIndex`, `aria-controls`) |

Nothing was hidden with `overflow: hidden` and no overflow measurement was relaxed.

## 3. Verification

```bash
cd apps/web && npm run typecheck     # exit 0
cd apps/web && npm run build         # exit 0, JS 342.10 kB (108.92 kB gzip)
npm run preview -- --port 4173 --strictPort
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-responsive.mjs   # exit 0
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/diag-overflow.mjs       # 360/360, 390/390
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-shell.mjs        # exit 0
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-tabs.mjs         # exit 0
```

Measured after:

```
issues: 0 | measured: 21 | docOverflow: 0 | kv squeezed: 0 | dir!=rtl: 0
360/dashboard doc: 360/360 | topbar: 360/360
360/settings  doc: 360/360 | topbar: 360/360
390/news      doc: 390/390 | topbar: 390/390
drawer: {"focusMovedInside":true,"focusedItem":"داشبورد","focusReturnedTo":"باز کردن منو","closed":true}
mobileSearch: {"rowVisible":true,"focusedLabel":"جست‌وجوی سراسری (موبایل)"}
```

Regression caught during this stage: the first drawer rewrite set `transition: visibility .18s`,
which kept the panel `visibility:hidden` at the moment React focused it, and `verify-shell` reported
`focusMovedInside: false`. The transition was split (immediate on open, delayed on close) and the
same script then reported `true`; the check was not weakened.

## 4. Known gaps

| Severity | Gap |
|---|---|
| `LOW` | With `MOCK_MODE` and no seeded data, no table is wide enough to actually scroll in the sweep, so the keyboard-scroll path is verified by structure (`tabIndex`/`role`) rather than by scrolling a 20-column table |
| `LOW` | 1024px is checked for layout only; the 1024–1280 band (sidebar visible + dense tables) has no dedicated screenshot baseline |
| `LOW` | Tap-target minimum is 34px for icon buttons on small screens (below the 44px recommendation) — a deliberate density trade-off to keep the topbar on one row at 360px |

**Next stage:** `F03.UX.7`, then `F03.0` (Control Plane backend) and `F12.1.1`.
