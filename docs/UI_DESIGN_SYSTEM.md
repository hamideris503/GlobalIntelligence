# UI Design System (HTML-aligned)

## Source of truth
`docs/GlobalIntelligence_WorldMonitor_2D_Full_Map.html` (CSS `:root` block, lines 2-48).

## Tokens (dark)
- `--bg: #060b15`, `--panel: #0c1728`, `--panel2: #101e32`, `--panel3: #14243a`
- `--line: rgba(151,180,220,.13)`, `--line2: rgba(151,180,220,.22)`
- `--text: #edf4ff`, `--muted: #93a5c1`, `--dim: #687d9c`
- Accents: `--blue:#5b91ff`, `--cyan:#35d7e8`, `--violet:#a18bff`, `--green:#45d6a0`, `--amber:#f6b85d`, `--red:#ff7187`
- `--radius: 15px`, `--font: 'Vazirmatn','Segoe UI',Tahoma,Arial,sans-serif`, `--shadow: 0 18px 55px rgba(0,0,0,.28)`

## Layout
- Sidebar: 256px fixed (76px collapsed), right side (RTL)
- Topbar: 76px sticky
- Content: max 1780px, padding 26px 28px
- Breakpoints: 1200 / 900 / 640

## Components
`.panel`, `.btn` (`.primary/.ghost/.small/.danger`), `.tag`, `.status` (`.s-green/.s-blue/.s-amber/.s-red/.s-violet`), `.metric`, `.table-wrap`, `.drawer`, `.palette`, `.toast`, `.filterbar`, `.grid-2/3/4`, `.executive`, `.synthesis`, `.network`, `.score-card`, `.pipeline`.

## Mapping to project tokens
Project tokens (`--bg`, `--surface`, etc.) were re-pointed to HTML palette in `apps/web/src/design/tokens.css` so existing components adopt the new colors without markup changes. HTML classes added as override layer in `apps/web/src/styles.css`.