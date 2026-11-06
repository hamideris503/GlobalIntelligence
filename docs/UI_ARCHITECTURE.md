# UI Architecture

## Shell
Single `Shell` component (`apps/web/src/ui.tsx`) wraps all routes. Structure (HTML-aligned):

```
.app.layout
├── aside.sidebar (fixed, 256px)
│   ├── .brand (.brand-mark + .brand-name/.brand-sub)
│   ├── nav (NAV_GROUPS from router.ts)
│   └── .sidebar-foot
├── (scrim when mobile open)
└── .main
    ├── header.topbar (.crumb, .global-search, .top-icon, .avatar, TopStatus)
    ├── (mobile search row)
    ├── main#main-content.content (route children)
    └── sr-only announce
```

## Routing
Hash-based (`src/router.ts`), 34 routes. No server-side routing changes. Refresh-safe (hash preserved).

## State
- API key: in-memory only (`localStorage` key string, never the secret value stored server-side; key value held in memory via `api.ts`).
- Theme: `theme-context.ts`.
- Collapsed sidebar, mobile open: local component state (not persisted; could be persisted to non-sensitive browser storage later).

## Data
All data via existing `api.ts` client to FastAPI backend. No mock data in production path. Loading/error/empty states via `Section`/`Spinner`/`Err`.

## Design system
See `UI_DESIGN_SYSTEM.md`. Tokens in `src/design/tokens.css`. Override layer in `src/styles.css`.