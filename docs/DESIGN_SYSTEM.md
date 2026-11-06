# Design System — F03.UX.1

Single source of truth for visual tokens and shared components of the GlobalIntelligence web app.
Anything visual belongs here or in `apps/web/src/design/tokens.css`; pages must not invent colours,
spacing, badges or status vocabularies.

**Scope of this stage:** tokens + four primitives (`FormField`, `Tabs`, `PriorityBadge`, shared
priority/status colour vocabulary) with real consumers. No page was redesigned, no dependency was
added, no backend/API contract changed.

---

## 1. Where tokens live

| File | Role |
|---|---|
| `apps/web/src/design/tokens.css` | **only** place to define token values (light + dark) |
| `apps/web/src/styles.css` | consumes tokens; component classes (`.badge`, `.panel`, `.field`, `.tabs`) |
| `apps/web/src/tw.css` | Tailwind utilities **only for the chat components**; it must never redefine an existing token (a self-referential `--font-sans: var(--font-sans)` here is what broke the Persian font stack, UX-16) |

Rule: a literal colour, radius, duration or z-index inside a page/component is a defect. Use a token.

---

## 2. Token contract

### 2.1 Colour and surface

| Token | Meaning |
|---|---|
| `--bg`, `--bg-elev` | page background / elevated background (sidebar, inputs) |
| `--surface`, `--surface-2` | card surface / subtle inner surface |
| `--border`, `--border-strong` | default divider / emphasised border |
| `--fg`, `--fg-2`, `--muted` | primary text / secondary text / hints and metadata |
| `--brand`, `--brand-strong`, `--brand-soft`, `--on-brand` | primary action and its tints |
| `--ok`, `--warn`, `--bad`, `--info`, `--demo` | semantic feedback colours |

`--demo` is reserved for "sample/mock" labelling and must never be used as a status colour.

### 2.2 Priority (P0–P4)

| Token | Level | Meaning |
|---|---|---|
| `--priority-p0` | P0 | highest urgency |
| `--priority-p1` | P1 | high |
| `--priority-p2` | P2 | medium |
| `--priority-p3` | P3 | low |
| `--priority-p4` | P4 | lowest / routine |

- The vocabulary comes from the backend (`PriorityLevel` in `backend/api/schemas/ingestion.py`,
  `PRIORITY_RANK` in `domains/news/classifier.py`). The UI must not invent a mapping from
  `importance` (1–10) to P-levels; that mapping is a backend/domain decision.
- Colour is never the only signal: every priority is rendered as text `P0`…`P4`.
- Unknown/empty priority renders as `—` (never green, never a made-up level).

### 2.3 Status

`--status-queued`, `--status-running`, `--status-succeeded`, `--status-failed`, `--status-paused`,
`--status-disabled`, `--status-unknown`.

`unknown` (not checked / no data) is deliberately **not** the success colour.

### 2.4 Focus, motion, layering, elevation

| Group | Tokens | Rule |
|---|---|---|
| Focus | `--focus-color`, `--focus-width`, `--focus-offset` | `:focus-visible` uses `var(--focus-width) solid var(--focus-color)`; never remove the ring |
| Motion | `--motion-fast`, `--motion-base`, `--motion-slow`, `--ease` | short, purpose-driven only; `prefers-reduced-motion` disables all animation globally |
| Layering | `--z-sticky`, `--z-popover`, `--z-scrim`, `--z-sidebar`, `--z-modal`, `--z-toast` | pages must not hard-code z-index |
| Elevation | `--elev-1`, `--elev-2`, `--elev-3` | three levels only |

### 2.5 Typography, spacing, shape, layout

`--font-sans`, `--font-mono`; `--fs-xs`…`--fs-2xl`; `--sp-1`…`--sp-6`; `--r-sm`, `--r-md`,
`--r-lg`, `--r-pill`; `--sidebar-w`, `--sidebar-w-collapsed`, `--topbar-h`, `--content-max`.

Design breakpoints (documented, not tokens — CSS variables are invalid inside media queries):
`520`, `860`, `960`, `1024`, `1440`.

---

## 3. Shared components

All live in `apps/web/src/ui.tsx`; a component joins this file only when it has **two or more real
consumers**.

### 3.1 `Field` (form field)

```tsx
// Plain children — unchanged behaviour, implicit label association.
<Field label="دامنه" hint="مثال: example.com">
  <input value={domain} onChange={...} />
</Field>

// Render-prop — explicit id / aria-describedby / aria-invalid wiring.
<Field label="Feed URL" required error={errors.feed_url} hint="https://…">
  {({ id, describedBy, invalid }) => (
    <input
      id={id}
      aria-describedby={describedBy}
      aria-invalid={invalid}
      value={feed}
      onChange={...}
    />
  )}
</Field>
```

- Label, hint and error are programmatically associated (`aria-describedby`), satisfied by the
  render-prop form; the plain form keeps the previous implicit-label behaviour for compatibility.
- `required` renders a visual `*` that is `aria-hidden`; `required` itself must be conveyed by the
  control (`required` attribute / `aria-required`), not by the asterisk.
- The error text uses the semantic `--bad` colour and `.err-text`, never a bare red literal.

### 3.2 `Tabs`

```tsx
<Tabs
  idPrefix="news"
  ariaLabel="اخبار و رویدادها"
  value={tab}
  onChange={(v) => setTab(v as "articles" | "events")}
  tabs={[{ id: "articles", label: "اخبار" }, { id: "events", label: "رویدادها" }]}
/>
<div role="tabpanel" id="news-panel-articles" aria-labelledby="news-articles">…</div>
```

- Emits `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, roving `tabIndex`.
- Keyboard: `ArrowRight`/`ArrowLeft` follow visual direction (inverted automatically in RTL),
  `Home`/`End` jump to first/last, selection follows focus.
- The consumer is responsible for rendering `role="tabpanel"` with the matching `id`.
- Consumers today: `pages/news.tsx`, `pages/screening.tsx`.

### 3.3 `PriorityBadge`

```tsx
<PriorityBadge priority={row.priority} />           // P0..P4 from the backend
<PriorityBadge priority={row.priority} label="اهمیت" />
```

- Accepts `string | null | undefined`; case-insensitive; anything outside `P0..P4` renders `—`.
- Renders `class="badge badge-prio" data-priority="P0"` and always prints the level as text; the
  tooltip repeats the level for screen readers that ignore `title` is not a substitute — the text is.
- Consumers today: review queue and dispatch tables in `pages/screening.tsx`.

### 3.4 Existing primitives (unchanged API)

`Button`-by-class (`primary` / `.secondary` / `.danger` / `.ghost` / `.linkbtn`), `Table`
(client-side sort, `emptyText`), `Section` (panel + loading/error), `Modal`, `ConfirmDialog`,
`Badge` (`ok|warn|bad|info|demo`), `Toast`/`useToast`, `Empty`, `Err`, `Spinner`, `StateBanner`,
`MockTag`, `StatCard`, `PageHeader`, `LineChart`/`Bars`/`Donut`/`Sparkline`, `useApi`.

Still missing and intentionally deferred to later stages (no real consumer yet):
`Switch`, `Drawer`, `Pagination` (currently page-local in `screening.tsx`), `Tooltip`,
`Breadcrumb`, `Skeleton` as a standalone component.

---

## 4. Component rules

1. Every interactive element has an accessible name; icon-only buttons use `aria-label`.
2. Meaning is never carried by colour alone — status and priority always include text.
3. Loading uses the skeleton inside the final layout (no large jump); error states are human
   readable and never include stack traces or secret values.
4. Destructive actions use `ConfirmDialog` with the exact affected count and scope.
5. New components require: token-only styling, states `default/hover/active/focus/disabled/loading/error`,
   RTL check at 390px, and at least two consumers before being added to `ui.tsx`.

---

## 5. Verification of this stage

| Check | Command | Result |
|---|---|---|
| Types | `cd apps/web && npm run typecheck` | PASS (exit 0) |
| Lint (changed files) | `npx eslint src/ui.tsx src/pages/news.tsx src/pages/screening.tsx` | PASS (0 errors, 5 pre-existing `react-refresh` warnings in `ui.tsx`) |
| Lint (whole app) | `npm run lint` | **FAIL (pre-existing)** — 6 errors in `apps/web/e2e/pg-fullstack.spec.ts`, a file from 2026-10-31 that this stage did not touch |
| Build | `cd apps/web && npm run build` | PASS — `dist/assets/index-*.js` 329.44 kB (105.10 kB gzip) |
| Font defect gone | `AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/capture.mjs` | PASS — before `"Times New Roman"` → after `Vazirmatn, IRANSansX, system-ui, "Segoe UI", Tahoma, sans-serif` on all 21 captures |
| Tabs keyboard/ARIA | `AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-tabs.mjs` | PASS — 2 tabs, roving `tabIndex` (`0`/`-1`), RTL `ArrowLeft` selects the next tab, `Home` returns to the first, active `aria-controls` resolves to a real panel |
| No layout regression | capture `horizontalOverflow` | 0 of 21 captures overflow |
| Priority uses backend vocabulary | `grep -n '"P0"' backend/api/schemas/ingestion.py` | `PriorityLevel = Literal["P0"…"P4"]` |

Capture notes: the post-fix run was taken against the **built** bundle (`npm run preview -- --port 4173`) because the long-running Vite dev server kept serving a stale Tailwind output for `tw.css`. Browser console errors in that run are CORS blocks (`origin 4173` is not allowed by the backend's `origin 5173` allowlist) plus signed-out `401`s — none originate from application code.

Known limitation: there is no unit/component test runner in this project. Component behaviour is
verified through typecheck/lint/build plus browser-level checks; adding `vitest` +
`@testing-library/react` needs an explicit dependency decision (recorded as UX-21).
