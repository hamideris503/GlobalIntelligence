# F34 — E2E در CI (F-34)

**وضعیت:** VERIFIED (config) · **تاریخ:** 2026-10-29

## English summary

Added a separate `e2e` job to `.github/workflows/ci.yml` that sets up Python 3.12 + Node 20, installs
backend + frontend deps, installs Playwright Chromium, and runs `npm run test:e2e:fullstack` (the existing
full-stack config: real FastAPI app on SQLite + Vite, no outbound network). The `frontend` job now also
runs `npm run lint` and `npm run typecheck` before build. E2E was previously not executed in CI.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `ci.yml` YAML | jobs: backend, docker, e2e, frontend |
| `npm run test:e2e:fullstack` config | موجود (playwright.fullstack.config.ts) |
| اجرای راه‌دور CI | تأیید نشده (نیاز به run واقعی) |

## ۲) محدودیت صریح

- اجرای راه‌دور CI تأیید نشده (محیط محلی Python 3.14/Node installed).
- فقط fullstack.spec.ts اجرا می‌شود (testMatch)، نه screening-ops/settings-models.
