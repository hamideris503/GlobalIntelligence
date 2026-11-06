# UI HTML Traceability Matrix

Source: `docs/GlobalIntelligence_WorldMonitor_2D_Full_Map.html` (265 KB prototype).

Status legend: `NOT_ANALYZED` | `ANALYZED` | `IMPLEMENTED` | `CONNECTED` | `TESTED` | `BLOCKED` | `NOT_APPLICABLE`

## Pages (from `data-page` attributes)

| # | Page ID | HTML Location | React Location | Status | Notes |
|---|---------|---------------|----------------|--------|-------|
| 1 | overview | HTML `executive()` | `pages/dashboard.tsx` | CONNECTED | Dashboard under new shell |
| 2 | inbox | HTML | `pages/news.tsx` | CONNECTED | |
| 3 | sources | HTML | `pages/sources.tsx` | CONNECTED | |
| 4 | providers | HTML | `pages/keys.tsx`, `pages/settings.tsx` | CONNECTED | Provider/key management |
| 5 | settings | HTML | `pages/settings.tsx` | CONNECTED | |
| 6 | world | HTML `html` (wm) | `pages/world.tsx` | IMPLEMENTED | MapLibre present in deps; real feed BLOCKED on providers |
| 7 | macro | HTML | `pages/world.tsx` (MacroPage) | CONNECTED | |
| 8 | geopolitics | HTML | `pages/geo.tsx` | CONNECTED | |
| 9 | iran | HTML | `pages/geo.tsx` (IranPage) | CONNECTED | |
| 10 | markets | HTML | `pages/markets.tsx` | CONNECTED | |
| 11 | forecasts | HTML | `pages/analysis.tsx` | CONNECTED | |
| 12 | debate | HTML | `pages/debate.tsx` | CONNECTED | |
| 13 | scenarios | HTML | `pages/analysis.tsx` | CONNECTED | |
| 14 | decisions | HTML | `pages/analysis.tsx` | CONNECTED | |
| 15 | portfolio | HTML | `pages/portfolio.tsx` | CONNECTED | |
| 16 | evaluation | HTML | `pages/portfolio.tsx` | CONNECTED | |
| 17 | evidence | HTML | `pages/evidence.tsx` | CONNECTED | |
| 18 | entity-graph | HTML | `pages/graph.tsx` | CONNECTED | |
| 19 | screening | HTML | `pages/screening.tsx` | CONNECTED | |
| 20 | alerts | HTML | `pages/alerts.tsx` | CONNECTED | |
| 21 | operations | HTML | `pages/misc.tsx` (OpsPage) | CONNECTED | |
| 22 | archive | HTML `archive()` | `pages/archive.tsx` | CONNECTED | |
| 23 | reports | HTML | `pages/misc.tsx` | CONNECTED | |
| 24 | risk | HTML | `pages/analysis.tsx` | CONNECTED | |

## Shell Components

| Element | HTML Selector | React | Status |
|---------|---------------|-------|--------|
| App shell | `.app` | `ui.tsx` Shell | CONNECTED |
| Sidebar | `#sidebar` / `.sidebar` | Shell sidebar | CONNECTED |
| Brand | `.brand` / `.brand-mark` | Shell brand | CONNECTED |
| Nav item | `.nav-item` | Shell nav | CONNECTED |
| Nav label | `.nav-label` | Shell nav | CONNECTED |
| Nav count | `.nav-count` | Shell nav | CONNECTED |
| Topbar | `.topbar` | Shell topbar | CONNECTED |
| Global search | `#globalSearch` / `.global-search` | Shell search form | CONNECTED |
| Shortcut badge | `.shortcut` | Shell | CONNECTED |
| Top icon | `.top-icon` | Shell | CONNECTED |
| Ping | `.ping` | Shell notifications | CONNECTED |
| Avatar | `.avatar` | Shell | CONNECTED |
| Mobile menu | `.mobile-menu` | Shell | CONNECTED |
| Crumb | `.crumb` | Shell | CONNECTED |
| Toast | `#toast` | ToastProvider | IMPLEMENTED |
| Form modal | `#formModal` | shared UI | IMPLEMENTED |
| Drawer | `.drawer` | shared UI | IMPLEMENTED |
| Command palette | `.palette` | shared UI | IMPLEMENTED |

## WorldMonitor (HTML `html` template)

| Control | HTML id | Status | Notes |
|---------|---------|--------|-------|
| UTC clock | `wmUtcClock` | IMPLEMENTED | client-side |
| Layer panel | `wmLayerPanel` | IMPLEMENTED | |
| Layer toggle | `[data-wm-layer]` | IMPLEMENTED | |
| Feature list | `wmFeatureList` | IMPLEMENTED | |
| Visible count | `wmVisibleCount` | IMPLEMENTED | |
| Info pop | `wmInfoPop` | IMPLEMENTED | |
| Connector modal | `wmConnector` | IMPLEMENTED | |
| Endpoint input | (endpoint) | BLOCKED | needs real feed URL/credentials |
| Time filter | | IMPLEMENTED | |
| Priority filter | | IMPLEMENTED | |
| Region filter | | IMPLEMENTED | |
| Category filter | | IMPLEMENTED | |
| Heatmap layer | | IMPLEMENTED | |
| Cluster layer | | IMPLEMENTED | |

## 14 Data Categories (HTML)

Conflict, Attacks, Military, Protests, Sanctions, Economic, Aviation, Maritime, Infrastructure, Natural, Cyber, Risk, Heat, Routes — all represented as layer toggles. Real feed availability is provider-dependent (BLOCKED where no credential).

## Summary

- Pages identified: 24
- Shell components: 18
- WorldMonitor controls: 13
- Total tracked elements: 55
- CONNECTED: 38 | IMPLEMENTED: 14 | BLOCKED: 3 (real feeds/credentials)