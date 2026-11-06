# UI Removal Audit

## Legacy shell replaced
- Old `.layout`/`.sidebar`/`.topbar` visual styling overridden to HTML palette/layout via `styles.css` override layer.
- `Shell` component markup updated to HTML structure (brand-mark, nav-item, topbar, crumb, global-search, top-icon, avatar).

## Files NOT removed (intentionally)
Backend, routers, models, migrations, services, analysis engines, AI gateway, source registry, pipelines — all preserved per mission rules. Only UI shell styling/markup changed.

## Legacy UI files identified for future deletion (after page restyling)
- Duplicate CSS rules in `styles.css` pre-dating override (cosmetic; harmless)
- `tw.css` (Tailwind layer) — still used by some components; keep
- Old `.navitem`/`.navlabel`/`.navbadge`/`.brand-logo`/`.searchbox`/`.iconbtn`/`.statuspill` classes — aliased to HTML equivalents via override; can be removed once pages migrated to HTML classes.

## Verification
- No second parallel UI: single `Shell`, single router.
- No iframe of HTML.
- No standalone HTML page in app runtime (HTML kept only as reference doc).