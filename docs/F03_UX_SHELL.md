# F03.UX.2 — App Shell & Navigation

**Stage:** `F03.UX.2`
**Status:** `PARTIALLY_VERIFIED` — every shell behaviour below was measured in a real browser
against the production build; the remaining gaps are listed in §9.
**Scope:** app shell, navigation, focus management, 404 route, mobile search, status legibility.
No page content was redesigned, no API/DB/migration changed, no dependency added.

---

## 1. Before (evidence)

From `docs/UI_UX_AUDIT.md` (§3 navigation, §6 responsive, §7 accessibility):

- Navigation grouped by internal domain, 25 items in 5 groups; `Settings` and `Archive` were
  untranslated inside a Persian menu; three items shared the `ops` icon.
- Global search `.searchbox` was `display:none` below 960px with **no replacement** (`UX-07`).
- Unknown hash silently rendered the dashboard (`UX-09`).
- Route changes left focus on the sidebar button; drawer left focus behind the scrim (`UX-10`).
- Status pills lost their text below 860px, leaving colour-only dots (`UX-14`).

## 2. After (measured)

`node docs/audit-baseline/verify-shell.mjs` against `npm run preview` (built bundle):

| Check | Result |
|---|---|
| Nav groups | `نمای کلی / هوشمندی / تحلیل / بازار و تصمیم / ورودی داده / عملیات / اتصالات و تنظیمات` |
| Untranslated labels | `[]` (Settings → تنظیمات، Archive → بایگانی و بازیابی) |
| Unique icons | `26/26` — every nav item has a distinct icon (`filter`, `archive` added) |
| Skip link | present, text `پرش به محتوای اصلی`, jumps to `#main-content` |
| Focus after navigation | `MAIN#main-content` |
| Screen-reader announcement | `به «منابع اطلاعاتی» منتقل شدید.` |
| Unknown hash `#/does-not-exist` | renders `صفحه یافت نشد` with 3 recovery actions |
| Mobile: desktop search hidden | `true` |
| Mobile: search button visible | `true` |
| Mobile search row | visible, input focused (`جست‌وجوی سراسری (موبایل)`) |
| Mobile status label | text `قطع` retained in DOM, visually hidden (`position:absolute; 1px`) |
| Drawer open | focus moves inside sidebar (first item: `داشبورد`) |
| Drawer Escape | closes and returns focus to `باز کردن منو` |

## 3. Files changed

| File | Change | Requirement |
|---|---|---|
| `apps/web/src/router.ts` | task-based `NAV_GROUPS` (7 groups), translated labels, unique icons; `notfound` route for unknown hashes | UX-05, UX-09 |
| `apps/web/src/icons.tsx` | `filter`, `archive` icons | UX-05 |
| `apps/web/src/App.tsx` | renders `NotFoundPage` for `notfound` | UX-09 |
| `apps/web/src/pages/misc.tsx` | `NotFoundPage` with recovery actions | UX-09 |
| `apps/web/src/ui.tsx` | skip link, route focus + live announcement, mobile search row, drawer focus in/out, `aria-expanded` on triggers, dialog focus trap and focus return, `titleForRoute` | UX-07, UX-10 |
| `apps/web/src/styles.css` | `.sr-only`, `.skip-link`, `.msearchrow`, topbar title mobile-only, status label visually hidden instead of removed | UX-07, UX-14 |

## 4. Architecture decisions

- **Route names unchanged.** Only labels and grouping changed, so bookmarks, deep links and E2E
  selectors keep working (verified: `e2e/*.spec.ts` do not select nav labels).
- **`notfound` is a real route state**, not a redirect, so the URL stays visible and the user can
  recover without losing context.
- **Focus moves to `<main tabIndex={-1}>`** rather than to the page `<h1>`: it works for pages
  without an `h1` and keeps the whole document readable from the top of the content.
- **Rejected:** adding a command palette/`cmdk` dependency (not required by this stage, and the
  spec forbids new dependencies without a demonstrated need); converting the shell to a nested
  router (breaks hash deep links used by existing pages).
- **Mobile status pills keep their text in the accessibility tree** (`.sr-only` pattern) instead of
  inventing a second tooltip-only surface.

## 5. Verification commands and results

```bash
cd apps/web && npm run typecheck                     # exit 0
cd apps/web && npx eslint src/ui.tsx src/router.ts src/App.tsx src/icons.tsx src/pages/misc.tsx
                                                     # 0 errors, 5 pre-existing react-refresh warnings
cd apps/web && npm run build                         # exit 0, JS 332.49 kB (106.08 kB gzip)
npm run preview -- --port 4173 --strictPort
AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-shell.mjs   # exit 0, results in §2
```

Notes:

- `npm run lint` for the whole app still fails on 6 pre-existing errors in
  `apps/web/e2e/pg-fullstack.spec.ts`, a file untouched by this stage.
- The 4173 preview produced console CORS errors because the backend allows origin 5173; those are
  harness artifacts, not application errors.

## 6. Manual checks

| Check | Status |
|---|---|
| Keyboard-only navigation of the sidebar and mobile drawer | RUN (Playwright keyboard) |
| Focus visible after route change and on skip link | RUN |
| RTL rendering of new group titles and focus ring | RUN (visual, RTL direction asserted) |
| Screen reader announcement | PARTIAL — the live region text is asserted in DOM, no screen reader used |
| 360/390/768/1024/1440 layout of the new shell | PARTIAL — 390 and 1440 asserted programmatically; 360/768/1024 not captured this stage |

## 7. Security review

No secret, credential, authorization or SSRF path touched. The search input only forwards a query
string to the existing `#/search` route; no new network surface was added.

## 8. Migration / rollback

None — frontend-only, no schema or API change. Reverting the six files restores the previous shell.

## 9. Known gaps

| Severity | Gap |
|---|---|
| `MEDIUM` | `UX-02` (one auth failure producing up to 8 identical error panels) is a page/state concern and belongs to UX.5 |
| `MEDIUM` | No visual regression harness; shell screenshots are only captured on demand |
| `LOW` | Command palette and document-wide shortcuts still missing (not required by this stage) |
| `LOW` | Drawer does not trap Tab inside the sidebar (Escape/close behaviour is correct); trapping a navigation drawer is optional, and `aria-modal` was deliberately not set |

**Next stage:** `F03.UX.3` — Dashboard KPIs with definitions, `last_updated_at`, and links into
filtered lists (`UX-03`, `UX-19`).
