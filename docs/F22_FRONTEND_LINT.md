# F22 — frontend lint/typecheck (F-22)

**وضعیت:** VERIFIED · **تاریخ:** 2026-10-29

## English summary

Frontend now has real, passing lint and typecheck instead of a missing ESLint dependency:
- Added ESLint 9 (flat config `eslint.config.js`) with `@eslint/js`, `typescript-eslint`,
  `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`.
- Added `"typecheck": "tsc --noEmit"` and `"check"` scripts; `npm run lint` and `npm run typecheck`
  both exit 0 (lint: 12 warnings, 0 errors).
- Fixed 5 real errors: 2 `no-explicit-any` in `settings.tsx`, setState-in-effect in `ui.tsx`/`response.tsx`
  (deferred via `queueMicrotask`), and an immutability violation in `Donut` (precomputed offsets).
- CI `frontend` job now runs `npm run lint`, `npm run typecheck`, then `npm run build`.
- Build still passes (324 kB, 24.7s).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `npm run lint` | 0 errors, 12 warnings, exit 0 |
| `npm run typecheck` | 0 errors, exit 0 |
| `npm run build` | exit 0 (324.6 kB) |
| CI frontend step | lint + typecheck + build |

## ۲) محدودیت صریح

- 12 warning (react-refresh/only-export-components) باقی ماندند — غیرمسدودکننده.
- ESLint 9 deprecated warning در npm (نسخهٔ 9 دیگر supported نیست)؛ ارتقا به 10 نیاز به config migration دارد.
- `.pytest_cache` در `apps/web` (permission-denied) در `.gitignore` پوشش داده شده است.
