# Frontend Platform — GlobalIntelligence

## Stack
React 18 + Vite 5 + Tailwind 4, RTL/Persian/dark. Tables only (no charts v1 except map canvas).

## App Shell
`apps/web/src/App.tsx`, `router.ts`, `ui.tsx`, `theme.tsx`, `theme-context.ts`, `design/tokens.css`. Shared: Navigation, Route Management, Page Layout, Theme, Design Tokens, Typography, Icons, Buttons, Tables, Filters, Forms, Modals, Drawers, Toasts, Loading/Empty/Error states, Permissions, API client, Query state, Notifications.

## Module boundaries
Page -> Components -> API functions (`api.ts`) -> Types (`types.ts`) -> Hooks/State. No God components.

## Design system
`apps/web/src/components/ui/*`, `docs/DESIGN_SYSTEM.md`. WCAG 2.2 AA targets (keyboard nav, focus states, readable typography, consistent spacing, empty/error/loading).

## Quality gates
typecheck 0 errors, lint 0 errors (warnings allowed), build success. Current: 1963 modules, 361.96 kB JS.
