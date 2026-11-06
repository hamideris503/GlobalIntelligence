# Local Runbook — GlobalIntelligence

## Prerequisites
Python >=3.11, Node 20+, PostgreSQL 16 (optional; SQLite fallback), Docker (optional).

## Setup
```
cp .env.example .env   # MOCK_MODE=true default
python scripts/check_env.py
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
cd apps/web && npm ci
```

## Run
```
# backend (from repo root)
uvicorn backend.main:app --reload
# frontend
cd apps/web && npm run dev
# full stack
docker compose up -d --build
```

## DB
```
python -m alembic upgrade head          # from repo root
docker compose exec backend python -m db.seed.sources
```
Postgres container: `gi_postgres` on 127.0.0.1:15432, DB `globalintelligence`.

## Tests
```
cd backend && python -m pytest ../tests -q          # full
cd backend && python -m pytest ../tests/test_<name>.py -q
ruff check backend domains tests scripts source_bot
cd apps/web && npm run typecheck && npm run lint && npm run build
```

## Verification baseline (2026-11-05)
Ruff clean; frontend typecheck/lint/build clean; backend subset 53 passed; full suite historically 1548 passed/1 skipped (SQLite).
