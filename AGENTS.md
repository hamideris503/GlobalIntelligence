# AGENTS.md — GlobalIntelligence

Modular monolith (FastAPI) + workers + React/Vite frontend + PostgreSQL + pinned n8n. Evidence-driven, free-first, mock-first. Core rule: deterministic compute in Python, interpretation via LLM, all AI through AI Gateway.

## Layout

- `backend/` — FastAPI app. Entrypoint `backend/main.py:create_app()` (`app = create_app()`). Routers in `backend/api/routers/` (45 routers), business logic in `domains/` and `backend/ai/` (`backend/services/` is an empty placeholder — `.gitkeep` only), `backend/ai/gateway/` + `backend/ai/providers/` (mock, gemini, openai, anthropic, openrouter, local_decision), plus `backend/ai/dispatch/` (durable article→task queue: routing/service/runner), `backend/ai/local_screening/` + `backend/ai/local_runtimes/` (Kev/Laya advisory screening and their supervisor) and `backend/ai/free_policy.py`. Analytical domains in `domains/`, background jobs run in-process via FastAPI `BackgroundTasks` (`source_bot/jobs.py`) and n8n workflows (`workers/` is still an empty placeholder — `.gitkeep` only).
- `backend/static/` — single-file HTML UI (RTL/Persian/dark), served by FastAPI at `/`.
- `db/migrations/` — Alembic scripts (`alembic.ini`: `script_location = db/migrations`). Seed via `python -m db.seed.sources`.
- `tests/` — 128 `test_*.py` files (~1570 tests), `conftest.py` is source of truth. `integrations/n8n/workflows/` — n8n JSON. `scripts/` — ops helpers. `config/*.toml` — env/debate config.
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
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest tests -q
pytest tests/test_<name>.py -q            # single file; -k for single test
```

CI has 5 jobs: `backend` (Python 3.12, postgres:16 service, `MOCK_MODE=true`, ruff + migrations up/down/up + **full suite** `pytest tests -q`), `backend-sqlite` (`-m "not pg"`), `docker` (builds both images), `e2e` (Playwright full-stack), `frontend` (Node 20, `npm ci || npm install && npm run lint && npm run typecheck && npm run build`). Both lanes are green locally as of 2026-11-04 — PG 1573 passed / 0 failed on a database migrated from an empty schema, SQLite 1570 passed / 1 PG-only skip — see `docs/qa/QA_BASELINE.md`. **Current caveat:** that is a local measurement on Python 3.14 / pytest 9.1.1 while CI pins 3.12 / pytest<9, so a remote CI run is still unverified; `alembic downgrade base` (which CI runs) was not repeated on the test lane.

## Conventions & gotchas

- **Python ≥3.11, line-length 100, ruff `E,F,I,UP,B`** (`ruff.toml` + `backend/pyproject.toml` identical). Ignored: `B008` (FastAPI `Depends()` idiom), `E501` (formatter owns it), `UP042`, `RUF012`, `PERF102`, `TRY004`. First-party: `backend,domains,tests`. No mypy in CI — don't add new gates.
- **Tests bypass auth and DB**: `tests/conftest.py` forces `API_KEY=""`, `MOCK_MODE=true`, shared in-memory SQLite (`StaticPool`), wipes all tables + resets `get_settings` cache and gateway singleton per test. New tests get this free — don't create separate engines/overrides. Pytest: `asyncio_mode=auto`, `testpaths=["../tests"]` (relative to `backend/`).
- **Auth**: every endpoint except `/health` (and login) requires `X-API-Key` header. Frontend sends user-typed key from `localStorage` directly — no backend proxy. Prod startup fail-fasts on weak/missing `SECRET_KEY`/`API_KEY`/`MOCK_MODE` (`validate_production()`); `/docs` disabled in prod.
- **DB resilience**: `/health/db` returns `degraded` without Postgres — server must not crash. `DATABASE_URL` with `psycopg` driver in Docker/CI.
- **Mock-first, never fake production**: `MOCK_MODE=true` / `AI_DEFAULT_PROVIDER=mock` is dev default. Missing provider key → provider disabled + fallback, no crash. In production mock is stripped from the chain — a real provider is required; classifier rejects mock results in prod. Flagged mock rows are never auto-deleted (needs user approval).
- **Deterministic core**: stats (Brier/LogLoss/VaR/Monte Carlo, importance via `compute_importance`, `verify_status` matrix) in pure Python; LLM only classifies/extracts via structured schemas. Return `INSUFFICIENT_EVIDENCE` when evidence is thin — no fake precision (number without source/time/uncertainty is forbidden).
- **Screening is advisory**: Kev/Laya output is written to `classification_meta` and never replaces deterministic rules or the cloud classifier; it is off by default and its probabilities must keep their model/source provenance. `AI_DEFAULT_PROVIDER`-level free policy (`ai/free_policy.py`) exempts local providers from the free-quota only.
- **Dispatch is durable and idempotent**: one `ArticleDispatch` row per `(article_id, task_name)`; only `pending/retryable` due rows are claimable; retries are bounded and end in `terminal`. Never add a second writer that bypasses `DispatchService`.
- **Point-in-time integrity**: always record `published_at/retrieved_at/available_at/observed_at/revision_at`; backtests use walk-forward/rolling only, never random shuffle.
- **Ingestion/dedup**: `Document` (raw) saved before any processing; uniqueness is per-source `(source_id, hash, content_hash)` — never global content_hash (destroys independence signal). Dedup = stdlib shingling+MinHash+LSH+Union-Find, detection not deletion (`duplicate_cluster`). `corroborated` needs ≥2 *independent* sources, not mentions.
- **n8n pinned `2.42.6`**: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is required (workflows read key from `$env` → `BACKEND_API_KEY`). Workflows import with `active:false`; never hardcode keys in workflow JSON.
- **Env/secrets**: `.env` never committed (gitignored with `backups/`, `*.dump`, `*.manifest.json`). Never print secret values; `docker compose config` leaks secrets. Never transfer `.env` to VPS — deploy script (`scripts/deploy_vps.py`) is dry-run by default per ADR-0057. `APP_ENCRYPTION_KEY` (Fernet) required for settings-panel key storage.
- **Style**: `.editorconfig` — utf-8, LF (CRLF only for bat/ps1), spaces (4 py / 2 js-ts-yml), final newline. Docs are bilingual (Persian + English) — keep that for user-facing docs.
