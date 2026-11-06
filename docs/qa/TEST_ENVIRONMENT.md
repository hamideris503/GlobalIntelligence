# Test Environment — GlobalIntelligence v1.5 QA

**Recorded:** 2026-11-04 · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`

## 1) Actual environment (measured, not assumed)

| Item | Value | How measured |
|---|---|---|
| OS | Windows (Git Bash shell), workspace `J:\Documents\GlobalIntelligence` | shell |
| Python | 3.14.4 (`.venv`) | `python --version` |
| Node / npm | v24.16.0 / 11.13.0 | `node --version`, `npm --version` |
| Docker | 29.8.2 available | `docker --version` |
| `psql` CLI | not installed on host | `psql --version` → not found |
| Alembic heads | single head `b8c4d5e6f7a8` | `alembic heads` |
| Pytest config | `asyncio_mode=auto`, `testpaths=["../tests"]`, markers `migration`, `pg` | `backend/pyproject.toml` |

## 2) Logical environment profiles (QA plan §1.3)

| Profile | Use here | External access | Data mutation |
|---|---|---|---|
| `local-readonly-audit` | git/status, file inspection, doc review | no | no |
| `test-sqlite` | default suite (`conftest.py`, in-memory SQLite + `StaticPool`) | no | test data only |
| `test-postgres` | PG lane when a local PG instance is reachable | no | test data only |
| `mock-network` | SSRF/adapter/provider failure injection (fake transport) | simulated | test data only |
| `local-e2e` | Playwright full-stack configs | localhost only | test data only |
| `optional-live-provider` / `telegram-test` | **not used this run** | would need owner credentials | — |

## 3) Isolation guarantees in the suite

- `tests/conftest.py` forces `API_KEY=""` and `MOCK_MODE=true`, wipes all tables per test and
  resets the settings cache and gateway singleton.
- Network is pinned offline: `source_verify.resolve_host_ips` / `source_bot.security` resolution is
  patched and reserved TLDs (RFC 6761) are closed at `socket.getaddrinfo`.
- Temp root is per-run (`PYTEST_DEBUG_TEMPROOT=gi-pytest-<pid>-*`) so parallel/repeat runs do not
  collide on the shared Windows `pytest-current` symlink (see `tests/test_temp_isolation.py`).
- No test touches the owner's real database, `.env`, or any live service.

## 4) Commands used (exact)

```bash
# backend suite (SQLite lane)
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider

# focused regression (this run)
.venv/Scripts/python.exe -m pytest \
  tests/test_ingest_jobs.py::test_job_runs_active_unique_index_blocks_second_active_row \
  "tests/test_source_bot_adapters_phase4.py::test_rest_json_conditional_headers_survive_adapter_rebuild" -q

# static
.venv/Scripts/python.exe -m ruff check backend domains tests scripts source_bot

# frontend
cd apps/web && npm run lint && npm run typecheck && npm run build
```

## 5) Not available in this environment

- Live PostgreSQL lane: no `psql` client and no confirmed running local PG instance at audit time.
  PG-gated tests must be reported `NOT RUN`/`BLOCKED` here, never as PASS.
- Live provider verification (F03), SMTP alert send, Telegram archive round-trip:
  `BLOCKED_EXTERNAL_CREDENTIAL`.
