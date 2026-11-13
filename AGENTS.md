# AGENTS.md — GlobalIntelligence

Modular monolith (FastAPI) + in-process background jobs + single-file HTML UI (`backend/static/index.html`) + PostgreSQL + pinned n8n. Evidence-driven, free-first, mock-first. Core rule: deterministic compute in Python, interpretation via LLM, all AI through AI Gateway.

## Layout

- `backend/` — FastAPI app. Entrypoint `backend/main.py:create_app()` (`app = create_app()`). Routers in `backend/api/routers/` (no hard-coded counts — measure with `grep -rc '@router\.' backend/api/routers`), business logic in `domains/` and `backend/ai/`, `backend/ai/gateway/` + `backend/ai/providers/` (mock, gemini, openai, anthropic, openrouter, local_decision), plus `backend/ai/dispatch/` (durable article→task queue: routing/service/runner), `backend/ai/local_screening/` + `backend/ai/local_runtimes/` (Kev/Laya advisory screening and their supervisor) and `backend/ai/free_policy.py`. Analytical domains in `domains/`, background jobs run in-process via FastAPI `BackgroundTasks` (`source_bot/jobs.py`) and n8n workflows (there is no separate worker service).
- `backend/static/` — single-file HTML UI (RTL/Persian/dark), served by FastAPI at `/`.
- `db/migrations/` — Alembic scripts (`alembic.ini`: `script_location = db/migrations`). Seed via `python -m db.seed.sources`.
- `tests/` — `test_*.py` files (counts drift — take the number from the latest `pytest tests -q` run, don't hard-code), `conftest.py` is source of truth. `tests/e2e/` holds three Playwright specs that are **not** run by CI (see below). `integrations/n8n/workflows/` — n8n JSON. `scripts/` — ops helpers. `config/*.toml` — env/debate config.
- Docs that matter: `ARCHITECTURE.md` (pipeline, entities, screening/dispatch flow), `DECISIONS.md` (ADRs — check before changing established patterns), `docs/ROADMAP_STAGE96_104.md` (current plan and per-stage exit criteria), `docs/FIXES_BACKLOG.md` (known defects/debt with evidence), `TASKS.md` (TODO/DONE status), `ROADMAP.md` (archive of phases 0–52).

## Commands (verify before deviating)

```bash
cp .env.example .env                      # first step, MOCK_MODE=true default
python scripts/check_env.py               # stdlib-only env check, exit 0/1
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload         # local backend (no Docker)
# UI is served by backend at / (single-file HTML in backend/static/)
docker compose up -d --build              # full stack: backend :8000, frontend :5173, n8n :5678
python -m alembic upgrade head            # run from repo root
docker compose exec backend python -m db.seed.sources
```

Verification order (mirrors CI in `.github/workflows/ci.yml`):

```bash
ruff check backend domains tests scripts source_bot
python scripts/check_legacy_ui_backup.py --live-only   # retired ui-data.* must stay absent
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest tests -q
pytest tests/test_<name>.py -q            # single file; -k for single test
```

CI has **3 jobs** (`.github/workflows/ci.yml`): `backend` (Python 3.12, postgres:16 service, `MOCK_MODE=true`, ruff + `check_legacy_ui_backup.py --live-only` (legacy UI guard) + migrations up/down/up + **full suite** `pytest tests -q`), `backend-sqlite` (`-m "not pg"`), `docker` (builds both images). There is **no `frontend` and no `e2e` job** — the Playwright specs in `tests/e2e/` and `package.json` exist but are not wired into CI, and `package.json` currently defines no `scripts`. Local measurements: PostgreSQL 16 **1814 passed / 0 failed** (2026-11-13, Python 3.14, 923.96 s, temp DB `gi_test_lane` dropped after, HEAD `ebe1292`); Playwright E2E **34 passed / 0 failed** (2026-11-13, local Chrome `chrome-win64/`, temp SQLite backend on :18100, HEAD `ebe1292` + UI offline-gate fix); SQLite **1813 passed / 1 skipped / 0 failed** (2026-11-13, Python 3.14, 442.98 s, HEAD `522522c` + working-tree changes); SQLite **1807 passed / 1 skipped / 0 failed** (2026-11-13, Python 3.14, 390.29 s); SQLite **1768 passed / 1 skipped / 0 failed** (2026-11-12, Python 3.14, 420.57 s); PostgreSQL 16 **1769 passed / 0 failed** (2026-11-12, Python 3.14, 1126.68 s, HEAD `aa5e000` on `step6a-analysis-dashboard`); earlier measurements: 1735 passed on HEAD `31b4ca4` + stage 6A (2026-11-06, 1501.89 s) and 1735 passed on the CI-pinned Python 3.12 container (2026-11-07, 1019.61 s, HEAD then `b7e1c2d3f4a5`). **Caveats:** a remote GitHub Actions run is still unverified, and `alembic downgrade base` was not repeated on the test lane.

## Conventions & gotchas

- **Python ≥3.11, line-length 100, ruff `E,F,I,UP,B`** (`ruff.toml` + `backend/pyproject.toml` identical). Ignored: `B008` (FastAPI `Depends()` idiom), `E501` (formatter owns it), `UP042`, `RUF012`, `PERF102`, `TRY004`. First-party: `backend,domains,tests`. No mypy in CI — don't add new gates.
- **Tests bypass auth and DB**: `tests/conftest.py` forces `API_KEY=""`, `MOCK_MODE=true`, shared in-memory SQLite (`StaticPool`), wipes all tables + resets `get_settings` cache and gateway singleton per test. New tests get this free — don't create separate engines/overrides. Pytest: `asyncio_mode=auto`, `testpaths=["../tests"]` (relative to `backend/`).
- **Auth**: every endpoint except `/health` (and login) requires `X-API-Key` header. Frontend sends user-typed key from `localStorage` directly — no backend proxy. Prod startup fail-fasts on weak/missing `SECRET_KEY`/`API_KEY`/`MOCK_MODE` (`validate_production()`); `/docs` disabled in prod.
- **DB resilience**: `/health/db` returns `degraded` without Postgres — server must not crash. `DATABASE_URL` with `psycopg` driver in Docker/CI.
- **Mock-first, never fake production**: `MOCK_MODE=true` / `AI_DEFAULT_PROVIDER=mock` is dev default. Missing provider key → provider disabled + fallback, no crash. In production mock is stripped from the chain — a real provider is required; classifier rejects mock results in prod. Flagged mock rows are never auto-deleted (needs user approval).
- **Deterministic core**: stats (Brier/LogLoss/VaR/Monte Carlo, importance via `compute_importance`, `verify_status` matrix) in pure Python; LLM only classifies/extracts via structured schemas. Return `INSUFFICIENT_EVIDENCE` when evidence is thin — no fake precision (number without source/time/uncertainty is forbidden).
- **Screening is advisory**: Kev/Laya output is written to `classification_meta` and never replaces deterministic rules or the cloud classifier; it is off by default and its probabilities must keep their model/source provenance. `AI_DEFAULT_PROVIDER`-level free policy (`ai/free_policy.py`) exempts local providers from the free-quota only.
- **Dispatch is durable and idempotent**: one `ArticleDispatch` row per `(article_id, task_name)`; only `pending/retryable` due rows are claimable; retries are bounded and end in `terminal`. An *unavailable prerequisite* (no screening runtime / no provider) is **not** a retry: the handler returns `blocked`, `DispatchService.mark_blocked` parks the row as `pending` with a growing backoff, refunds the claim's attempt and keeps the reason in `last_error` (`screening_unavailable:`). Bulk revive of such rows is `POST /api/dispatch/recover-screening` (admin, gated on a real provider → 409 otherwise). Never add a second writer that bypasses `DispatchService`.
- **Point-in-time integrity**: always record `published_at/retrieved_at/available_at/observed_at/revision_at`; backtests use walk-forward/rolling only, never random shuffle.
- **Ingestion/dedup**: `Document` (raw) saved before any processing; uniqueness is per-source `(source_id, hash, content_hash)` — never global content_hash (destroys independence signal). Dedup = stdlib shingling+MinHash+LSH+Union-Find, detection not deletion (`duplicate_cluster`). `corroborated` needs ≥2 *independent* sources, not mentions.
- **n8n pinned `2.42.6`**: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is required (workflows read key from `$env` → `BACKEND_API_KEY`). Workflows import with `active:false`; never hardcode keys in workflow JSON.
- **Env/secrets**: `.env` never committed (gitignored with `backups/`, `*.dump`, `*.manifest.json`). Never print secret values; `docker compose config` leaks secrets. Never transfer `.env` to VPS — deploy script (`scripts/deploy_vps.py`) is dry-run by default per ADR-0057. `APP_ENCRYPTION_KEY` (Fernet) required for settings-panel key storage.
- **Style**: `.editorconfig` — utf-8, LF (CRLF only for bat/ps1), spaces (4 py / 2 js-ts-yml), final newline. Docs are bilingual (Persian + English) — keep that for user-facing docs.
