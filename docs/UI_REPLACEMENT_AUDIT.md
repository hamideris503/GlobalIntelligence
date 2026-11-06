# UI Replacement Audit — GlobalIntelligence

**Date:** 2026-11-05
**Branch:** stage95-pg-ci-verification
**HEAD:** 42b2278e22deb19119bb8447db00bcaad4b549fb

## 1. Git Baseline

- Branch: `stage95-pg-ci-verification`
- HEAD: `42b2278e22deb19119bb8447db00bcaad4b549fb`
- Working tree: many modified/untracked files (pre-existing AI work — preserved, not reverted)
- No `git reset --hard` / `git clean` performed.

## 2. Source Inventory

### Frontend (`apps/web`)
- React 18 + Vite 5 + TypeScript, Tailwind 4, RTL/Persian
- Router: hash-based (`src/router.ts`), 34 routes
- Shell: `src/ui.tsx` `Shell` component
- Pages: 20+ in `src/pages/`
- Design tokens: `src/design/tokens.css`
- API client: `src/api.ts`

### Backend
- FastAPI modular monolith, 45 routers in `backend/api/routers/`
- AI Gateway + providers (mock, gemini, openai, anthropic, openrouter, local_decision)
- PostgreSQL + SQLite dual lane

### HTML Design Reference
- `docs/GlobalIntelligence_WorldMonitor_2D_Full_Map.html` (265 KB, 607 lines, single-file prototype)
- 24 pages identified via `data-page` attributes
- Design palette: `--bg:#060b15`, `--panel:#0c1728`, accent blue `#5b91ff`, cyan `#35d7e8`

### Roadmap
- `docs/GlobalIntelligence_Roadmap_v1.5_Full_Engineering_Spec.md` (3362 lines)

## 3. What Was Done

1. **Design token alignment**: `apps/web/src/design/tokens.css` dark theme palette updated to HTML's palette (`#060b15`/`#0c1728`/`#101e32`/`#14243a`, accent colors).
2. **HTML design CSS override**: appended to `apps/web/src/styles.css` — HTML's shell/layout/component classes (`.sidebar`, `.topbar`, `.content`, `.panel`, `.btn`, `.nav-item`, `.brand-mark`, etc.) now match the HTML prototype.
3. **Shell replacement**: `apps/web/src/ui.tsx` `Shell` rewritten to HTML structure:
   - Brand with `.brand-mark` + `.brand-name`/`.brand-sub`
   - Nav items use `.nav-item` / `.nav-label` / `.nav-count`
   - Topbar uses `.topbar`, `.crumb`, `.global-search`, `.top-icon`, `.avatar`, `.top-spacer`
   - Layout uses `.app` wrapper with HTML dimensions (256px sidebar, 76px topbar, 1780px content)
4. **TopStatus** preserved (system health + mock-mode indicator).

## 4. What Remains (see UI_LEGACY_FEATURE_MIGRATION / traceability matrix)

- Page-level markup restyling to HTML component classes (currently pages use project classes which are visually overridden).
- WorldMonitor map (MapLibre) full connection to real feeds — needs provider credentials.
- Full removal of unused legacy CSS/components after page restyling.
- E2E verification of all 24 HTML pages.

## 5. Files Changed

- `apps/web/src/design/tokens.css`
- `apps/web/src/styles.css`
- `apps/web/src/ui.tsx`
- `docs/GlobalIntelligence_WorldMonitor_2D_Full_Map.html` (copied for reference)