# AGENTS.md — GlobalIntelligence

Modular monolith (FastAPI) + workers + React/Vite frontend + PostgreSQL + pinned n8n. Evidence-driven, free-first, mock-first. Core rule: deterministic compute in Python, interpretation via LLM, all AI through AI Gateway.

## Layout

- `backend/` — FastAPI app. Entrypoint `backend/main.py:create_app()` (`app = create_app()`). Routers in `backend/api/routers/` (~40 domains), business logic in `backend/services/`, `backend/ai/gateway/` + `backend/ai/providers/` (mock, gemini, openai, anthropic, openrouter), analytical domains in `domains/`, background jobs in `workers/`.
- `apps/web/` — React 18 + Vite 5 + Tailwind 4, RTL/Persian/dark. No charts in v1, tables only.
- `db/migrations/` — Alembic scripts (`alembic.ini`: `script_location = db/migrations`). Seed via `python -m db.seed.sources`.
- `tests/` — ~65 `test_*.py` files, `conftest.py` is source of truth. `integrations/n8n/workflows/` — n8n JSON. `scripts/` — ops helpers. `config/*.toml` — env/debate config.
- Docs that matter: `ARCHITECTURE.md` (pipeline + entities), `DECISIONS.md` (ADRs — check before changing established patterns), `TASKS.md` (TODO/DONE status), `ROADMAP.md` (52 phases, all DONE except Phase 48 live which is BLOCKED without VPS).

## Commands (verify before deviating)

```bash
cp .env.example .env                      # first step, MOCK_MODE=true default
python scripts/check_env.py               # stdlib-only env check, exit 0/1
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload         # local backend (no Docker)
cd apps/web && npm ci && npm run dev      # frontend; npm run build for prod check
docker compose up -d --build              # full stack: backend :8000, frontend :5173, n8n :5678
python -m alembic upgrade head            # run from repo root
docker compose exec backend python -m db.seed.sources
```

Verification order (mirrors CI in `.github/workflows/ci.yml`):

```bash
ruff check backend domains tests scripts
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest tests -q
pytest tests/test_<name>.py -q            # single file; -k for single test
```

CI has 3 jobs: `backend` (Python 3.12, postgres:16 service, `MOCK_MODE=true`), `docker` (builds both images), `frontend` (Node 20, `npm ci || npm install && npm run build`).

## Conventions & gotchas

- **Python ≥3.11, line-length 100, ruff `E,F,I,UP,B`** (`ruff.toml` + `backend/pyproject.toml` identical). Ignored: `B008` (FastAPI `Depends()` idiom), `E501` (formatter owns it), `UP042`, `RUF012`, `PERF102`, `TRY004`. First-party: `backend,domains,tests`. No mypy in CI — don't add new gates.
- **Tests bypass auth and DB**: `tests/conftest.py` forces `API_KEY=""`, `MOCK_MODE=true`, shared in-memory SQLite (`StaticPool`), wipes all tables + resets `get_settings` cache and gateway singleton per test. New tests get this free — don't create separate engines/overrides. Pytest: `asyncio_mode=auto`, `testpaths=["../tests"]` (relative to `backend/`).
- **Auth**: every endpoint except `/health` (and login) requires `X-API-Key` header. Frontend sends user-typed key from `localStorage` directly — no backend proxy. Prod startup fail-fasts on weak/missing `SECRET_KEY`/`API_KEY`/`MOCK_MODE` (`validate_production()`); `/docs` disabled in prod.
- **DB resilience**: `/health/db` returns `degraded` without Postgres — server must not crash. `DATABASE_URL` with `psycopg` driver in Docker/CI.
- **Mock-first, never fake production**: `MOCK_MODE=true` / `AI_DEFAULT_PROVIDER=mock` is dev default. Missing provider key → provider disabled + fallback, no crash. In production mock is stripped from the chain — a real provider is required; classifier rejects mock results in prod. Flagged mock rows are never auto-deleted (needs user approval).
- **Deterministic core**: stats (Brier/LogLoss/VaR/Monte Carlo, importance via `compute_importance`, `verify_status` matrix) in pure Python; LLM only classifies/extracts via structured schemas. Return `INSUFFICIENT_EVIDENCE` when evidence is thin — no fake precision (number without source/time/uncertainty is forbidden).
- **Point-in-time integrity**: always record `published_at/retrieved_at/available_at/observed_at/revision_at`; backtests use walk-forward/rolling only, never random shuffle.
- **Ingestion/dedup**: `Document` (raw) saved before any processing; uniqueness is per-source `(source_id, hash, content_hash)` — never global content_hash (destroys independence signal). Dedup = stdlib shingling+MinHash+LSH+Union-Find, detection not deletion (`duplicate_cluster`). `corroborated` needs ≥2 *independent* sources, not mentions.
- **n8n pinned `2.42.6`**: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is required (workflows read key from `$env` → `BACKEND_API_KEY`). Workflows import with `active:false`; never hardcode keys in workflow JSON.
- **Env/secrets**: `.env` never committed (gitignored with `backups/`, `*.dump`, `*.manifest.json`). Never print secret values; `docker compose config` leaks secrets. Never transfer `.env` to VPS — deploy script (`scripts/deploy_vps.py`) is dry-run by default per ADR-0057. `APP_ENCRYPTION_KEY` (Fernet) required for settings-panel key storage.
- **Style**: `.editorconfig` — utf-8, LF (CRLF only for bat/ps1), spaces (4 py / 2 js-ts-yml), final newline. Docs are bilingual (Persian + English) — keep that for user-facing docs.
