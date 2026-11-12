# STEP 6A.42 — Browser Verification of Deferred Actions (Disposable DB)

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: close the browser-verification gap left open by STEP 6A.24/6A.27/6A.33/6A.35/6A.41 for `alerts`, `providers` and `portfolio`, and re-check the `evaluation` empty state, using a throwaway PostgreSQL database and a temporary backend on a free loopback port. No primary-DB writes, no paid AI calls, no external network, no git operations.

---

## 1. Repository Baseline and Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash |
| Primary DB `globalintelligence` | **0 writes.** Read-only counts before and after: alerts=1, alert_rules=1, portfolios=0, forecasts=37, forecast_outcomes=0, macro_assessments=24 (identical to the STEP 6A.41 baseline) |
| Disposable DB | `gi_qa_6a42` on `gi_postgres` (127.0.0.1:15432), 53 tables, `alembic upgrade head` exit 0, head `c8f2d3e4a5b6` |
| Temporary backend | `uvicorn backend.main:app` on `127.0.0.1:18099`, `APP_ENV=development`, `MOCK_MODE=true`, throwaway `API_KEY`, throwaway `APP_ENCRYPTION_KEY`, seeded throwaway admin |
| Active containers | `gi_backend_parity`, `gi_backend_cand_6a39`, `gi_frontend`, `gi_n8n`, `gi_staging_*` — untouched |
| `LOCAL_SCREENING_ENABLED` | unchanged (`false`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | **none** — no provider `/test` was executed |
| Real email / Telegram | none |
| Secrets printed | none (DB credentials were read inside the shell from the container env and never echoed) |

Why a disposable DB: alert ack/resolve, portfolio create/snapshot and provider register/toggle are genuinely mutating. Running them on `globalintelligence` would have changed the primary dataset that STEP 6A.41 froze (37 forecasts, 1 alert). The throwaway database is dropped at the end of the stage.

---

## 2. Endpoint and Authorization Contract (verified in code before the browser run)

| Item | Evidence |
|------|----------|
| Auth | Session cookie (`POST /api/auth/session`) or `X-API-Key`; `backend/auth/deps.py` |
| CSRF | Session POSTs require the CSRF header; the UI `api()` helper supplies it |
| Roles | `admin` needed for `/api/settings/*` writes; `analyst` for `/api/alerts/evaluate`; ack/resolve and portfolio writes are `admin` |
| Alert fixtures | 1 `alert_rules` row + 1 `alerts` row inserted directly into the disposable DB (metric `market:WTI`, status `active`) |
| Macro observations | **not** seeded in the disposable DB on purpose, so primary data is never copied |

---

## 3. Results per Page (browser, real backend, real session)

| # | Page | Action performed | Result |
|---|------|------------------|--------|
| 1 | `evaluation` | open page (n=0) | **VERIFIED** — renders `INSUFFICIENT_EVIDENCE · n = ۰`, no fabricated MAE/RMSE/Brier; footer states no number is invented |
| 2 | `alerts` | list fixture → click **تأیید** → click **حل** | **VERIFIED** — `POST /api/alerts/{id}/ack 200`, `POST /api/alerts/{id}/resolve 200`; row status went `active → resolved`, action cell switched to «حل شده» |
| 3 | `providers` | list env providers; create DB provider; click enable switch | **VERIFIED** — 4 `env:` providers rendered read-only; `POST /api/settings/providers 200` with `key_set=true`; switch issued the update and the row changed `فعال → غیرفعال` |
| 3a | `providers` | create with `http://` base_url | **422 rejected** (`base_url must use https`) — the security guard is correct, not a defect |
| 4 | `portfolio` | open → «پورتفوی جدید» form → submit → click name → «ساخت Snapshot» | **VERIFIED after fix (F1)** — list shows `۱ پورتفوی · ۲ موقعیت`, detail shows both positions, `POST .../snapshot 200` with `{"stored":0,"skipped":1}` (honest skip: no active forecast scenarios in the disposable DB) |
| 4a | `portfolio` snapshot | repeat | **VERIFIED** — still `skipped=1`, no fabricated snapshot row |
| 5 | `macro` | open → «تحلیل همه» | **VERIFIED after fix (F1)** — page renders country/indicator filters and the overview section; `POST /api/macro/analyze 200`; assessments stay at 0 because the disposable DB holds no macro observations (eligible series = 0) |
| 6 | `geopolitics` | open | **VERIFIED after fix (F1)** — real page (`تحلیل ژئوپلیتیک`) renders; `GET /api/geopolitics/assessments 200`, `GET /api/geopolitics/tensions 200` |

Console during the whole run: **two** `422` entries, both from the deliberate non-HTTPS provider attempt (§3.3a). No JS exceptions, no 401/500 after login, no failed asset loads.

---

## 4. F1 — Defect Found and Fixed (only product change in this stage)

**Symptom.** Navigating to `portfolio` rendered the `genericDomain('portfolio')` placeholder («مدیریت پرتفوی», «دادهٔ نمونه») instead of `portfolioPage()`. `#portfolioLive` did not exist, so `loadPortfolio()` returned immediately at its container guard: a real API-connected page silently degraded to a mock-looking screen. `macro` and `geopolitics` had the same defect.

**Root cause.** In `renderPage()` the chain ended with

```js
if(activePage==='ai-chat')html=aiChatPage();
else if(['geopolitics','macro','portfolio'].includes(activePage))html=genericDomain(activePage);
```

Because the `else if` binds to the `ai-chat` branch, it re-assigned `html` to the placeholder **after** the dedicated renderers above had already produced the real page. A previous stage had already narrowed the list from seven pages to three, which is why only these three still failed.

**Fix.** Replaced that stale branch with a comment; the dedicated `macro`/`portfolio`/`geopolitics` renderers and their `pageRenderers` entries are now authoritative.

**Evidence of the fix.**

| Check | Before | After |
|-------|--------|-------|
| `portfolio` `<h1>` | `مدیریت پرتفوی` (placeholder) | `پورتفوی` |
| `#portfolioLive` | missing | `پورتفوی‌ها ۱ پورتفوی · منبع: /api/portfolios` |
| `macro` `<h1>` | placeholder | `تحلیل کلان` + filters + overview |
| `geopolitics` `<h1>` | placeholder | `تحلیل ژئوپلیتیک` |
| `node --check` (both inline script blocks) | — | exit 0 / exit 0 |

**Regression guard.** New `tests/test_ui_page_wiring.py` asserts (a) no `else if([...].includes(activePage))html=genericDomain(activePage);` covers `macro`/`portfolio`/`geopolitics`, (b) each page keeps its dedicated branch and `pageRenderers` mapping, (c) every one of the 23 data-bearing pages has a loader whose first container id actually exists in that page's markup, (d) `renderPage()` only schedules loaders that are defined, and (e) `nf`/`nfV` are global and format Persian numbers correctly (null/NaN → «—», `B`/`M` suffixes, no «ناعدد») — (e) runs the real helper code in Node so the F3 class of bug cannot come back silently.

---

## 5. Deployed-versus-verified state (after activation — see §9)

| Artifact | SHA-256 |
|----------|---------|
| Working-tree `backend/static/index.html` | `7219363b901d08e2479dfda75474c626878493d4713beb35dcc2581e222bd144` |
| Baked image file (LF-normalized) in `candidate-step6a42-r3-20261111` | `6f5ececaf1d38f2852860a9b0061dbe7809d303a1d93629b02386ec46b6616e7` |
| Serving file in `gi_backend_parity` on `127.0.0.1:8000` | `6f5ececa…` — **matches the image** |
| Pre-activation container file | `6ed721c5…` (kept in rollback container) |

The renderer fix, the missing `nfV` helper and its formatting bug are now baked into a derived image and live on port 8000 (§9).

---

## 6. What was explicitly not done

| Item | Status | Why |
|------|--------|-----|
| Remote CI (Python 3.12 / pytest<9) | **NOT_RUN** | `gh` CLI is absent and pushing/running the workflow needs GitHub authorization; nothing was pushed |
| Geopolitics actor backfill | **NOT_RUN** | Requires a real AI provider (deterministic path deliberately abstains); primary DB has 0 assessments and no paid call is allowed in this stage |
| Evaluation scoring with real outcomes | **BLOCKED** | 0 `forecast_outcomes`; forecasts mature ~2026-12-11 |
| Provider connection test | **SKIPPED INTENTIONALLY** | The test button makes a real, billable provider call |
| Full-suite pytest | **NOT_RUN** | UI-only change; a focused guard test plus `node --check` covers it |

---

## 7. Changed Files

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | removed the stale `genericDomain` override for `macro`/`portfolio`/`geopolitics` (1 line) |
| 2 | `tests/test_ui_page_wiring.py` | new regression guard for page wiring |
| 3 | `docs/qa/STEP_6A_42_BROWSER_VERIFICATION_DEFERRED_ACTIONS.md` | this report |

Cleanup: temporary backend stopped, `gi_qa_6a42` dropped, `.tmp-qa-6a42*` artifacts removed.

---

## 8. Next Recommended Stage

1. **Activate the UI fix in Docker** (derived image from `source-parity-step6a15`) and re-run these six pages on port 8000 against the primary DB read-only paths.
2. **Forecast maturity (2026-12-11)** → `POST /api/outcomes/resolve?dry_run=false` → `POST /api/evaluation/run`; the Evaluation page is already implemented and will switch from `INSUFFICIENT_EVIDENCE` to real metrics.
3. **Provider browser run against a real key** (paid, needs user approval) to close the `/test` path.
4. **Remote CI** once GitHub execution is authorized.

STOP — one verification workstream completed; one real UI defect found and fixed; primary DB unchanged; disposable DB removed; no git operations.

---

## 9. Docker Activation and Re-verification on :8000

**Build strategy.** Derived image (`FROM candidate-step6a39-20261111` + `COPY` of the UI file only), because the standard from-scratch build is still blocked by the pre-existing PyPI issue. Line endings are normalized to LF per `.editorconfig` in a staged copy; the working-tree file itself was not rewritten. Only `backend/static/index.html` was replaced in the image — backend Python, dependencies and entrypoint are byte-identical to the previously verified runtime.

| Item | Value |
|------|-------|
| Base image | `globalintelligence-backend:candidate-step6a39-20261111` (`bf83d88c9148`) |
| r1 image | `candidate-step6a42-20261111` → `1a74bdb3018d` (renderer fix only) |
| r2 image | `candidate-step6a42-r2-20261111` → `f140409b2cad` (global `nfV`) |
| r3 image (active) | `candidate-step6a42-r3-20261111` → `09da78fa0ff6` (`nfV` formatting fixed) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000`, healthy, same env (17 vars), `bridge` network, same compose labels |
| Rollback containers | `gi_backend_parity_pre_step6a42` (candidate-step6a39, Exited 137), `gi_backend_parity_step6a42_r1` (r1), `gi_backend_parity_step6a42_r2` (r2) — all preserved |
| Auth on :8000 | No `API_KEY` in container env and `APP_ENV=development` → dev bypass: `/api/auth/me` = 200, ribbon `service · مدیر`, no credential typed anywhere |

**Read-only re-verification on :8000 (primary DB, no mutations).**

| Page | Result |
|------|--------|
| `evaluation` | `INSUFFICIENT_EVIDENCE · n = ۰` (`/api/evaluation/summary` → `n: 0`, all metrics null) |
| `alerts` | 1 real alert rendered (`POST /api/alerts/{id}/ack\|resolve` **not** clicked) |
| `providers` | catalogue + models render; 0 DB-registered providers on the primary DB |
| `portfolio` | real empty state, `#portfolioLive` present (`/api/portfolios` → `[]`) |
| `macro` | 29 table rows; overview `gdp 2025 ۱۹٬۴۹۸٫۰۴B`; no «ناعدد», no load error |
| `geopolitics` | real page, `GET /api/geopolitics/assessments` 200, no load error |

Primary DB counts unchanged before and after: alerts=1, alert_rules=1, portfolios=0, forecasts=37, forecast_outcomes=0, macro_assessments=24, geopolitical_assessments=0.

### F2 — `nfV is not defined` (macro / geopolitics / portfolio)
`nfV` existed only as a local helper inside `loadIranBrief`. `loadMacro`, `loadGeopolitics` and `loadPortfolioSnapshots` referenced a global that never existed, so the first real data row threw a `ReferenceError` and the whole page body was replaced by «خطا در دریافت … nfV is not defined». STEP 6A.42 missed it because its disposable DB had 0 macro assessments, so the formatting branch never executed. Fix: a global `nfV` helper next to `nf`.

### F3 — `nfV` printed «ناعدد»
The helper appended the `B`/`M` suffix **before** calling `Intl.NumberFormat`, so large values were formatted as `"30769.70B"` → `NaN` → «ناعدد». Fix: format the numeric part, then append the suffix. Verified on real data (`gdp 2025 ۱۹٬۴۹۸٫۰۴B`).

`node --check` on both inline script blocks of the served file: exit 0 / 0. No console errors on the six pages after the final reload.

**Test sensitivity (mutation probe).** Each fixed defect was re-injected into a copy of the file and the new tests were run against it: suffix-before-formatting (F3) → caught by both the static test and the Node test; global `nfV` removed so only the local helper remains (F2) → caught by the Node test (the static test alone is blind to it, which is why the runtime check exists); `genericDomain` override restored (F1) → caught; `#portfolioLive` removed from `portfolioPage()` → caught; loader typo (`loadPortfolioX`) → caught.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `renderPage()` overrode `macro`/`portfolio`/`geopolitics` with `genericDomain()` | **FOUND_AND_FIXED** |
| F2 | `alerts` ack/resolve work end-to-end in the browser | **VERIFIED** |
| F3 | `providers` list/create/enable-toggle work; `http://` base_url rejected (422) | **VERIFIED** |
| F4 | `portfolio` create-from-form, list, detail and snapshot work | **VERIFIED** |
| F5 | `evaluation` shows `INSUFFICIENT_EVIDENCE · n=۰` with no fabricated metric | **VERIFIED** |
| F6 | `macro` analyze runs; 0 assessments in a DB without macro observations | **VERIFIED** (expected) |
| F7 | `geopolitics` page and read endpoints render data-backed empty states | **VERIFIED** |
| F8 | No console errors except two deliberate 422s | **VERIFIED** |
| F9 | Primary DB untouched (counts identical to 6A.41) | **VERIFIED** |
| F10 | Container images still serve the pre-fix UI | **PENDING ACTIVATION** |
| F11 | Remote CI on Python 3.12 / pytest<9 | **NOT_RUN** |
| F12 | Geopolitics actor backfill | **BLOCKED** (needs real provider) |
| F13 | Renderer fix baked into a derived image and active on :8000 | **ACTIVATED** |
| F14 | Global `nfV` helper added (`ReferenceError` on real data rows) | **FOUND_AND_FIXED** |
| F15 | `nfV` suffix formatting produced «ناعدد» for large values | **FOUND_AND_FIXED** |
| F16 | Primary DB untouched during activation and re-verification | **VERIFIED** |
| F17 | Rollback images and containers preserved | **VERIFIED** |
| F18 | Full suite run in one invocation with the new guard tests | **PASSED** (1764 passed, 1 skipped, exit 0) |
| F19 | PostgreSQL lane on a disposable database | **PASSED** (1765 passed, 0 skipped, 0 failed, exit 0) |
| F20 | Python 3.12 + pytest<9 CI-equivalent lane | **PASSED** (tests and lint gate — lint debt cleared in §12.7) |

---

## 10. Full-Suite Regression Run (single invocation, SQLite lane)

Goal: prove the new guard file (`tests/test_ui_page_wiring.py`) does not interfere with `tests/conftest.py` or with any other test file.

```bash
./.venv/Scripts/python.exe -m pytest tests -q      # no DATABASE_URL set in the shell or in .env
```

Safety check before running: `DATABASE_URL` is absent, so `tests/conftest.py` builds the shared in-memory SQLite engine (`StaticPool`) and sets `API_KEY=""` / `MOCK_MODE=true`; the PostgreSQL database `globalintelligence` is never touched.

| Measurement | Result |
|---|---|
| Outcome | `1764 passed, 1 skipped, 697 warnings in 458.97s (0:07:38)` |
| Exit code | `0` |
| New guard file collected in the same run | yes — `pytest tests --collect-only -q` lists all six `test_ui_page_wiring.py` tests |
| `ruff check tests/test_ui_page_wiring.py` | clean |
| Interference with `conftest.py` fixtures | none observed (no errors, no cross-test leaks, no ordering dependency) |

Notes:

- The invocation had to run detached (`pytest ... > log`) because the local tool ceiling is ~295 s per command while the suite takes ~460 s; results above are read from that log, not from an interrupted run.
- The single skip is the pre-existing PG-only skip of the SQLite lane.
- **Not run in this invocation:** `alembic` up/down/up (covered in earlier stages) and remote CI (**F11 NOT_RUN**). The PostgreSQL lane is covered in §11. The local interpreter is Python 3.14 / pytest 9.x while CI pins 3.12 / pytest<9, so CI parity remains unverified.

---

## 11. PostgreSQL Lane versus SQLite Lane

Same suite, same `tests/conftest.py`, same single-invocation method; the only difference is whether `DATABASE_URL` points at PostgreSQL.

| Setup | Detail |
|---|---|
| Database | `gi_qa_pg_lane_6a42` created on `gi_postgres` (`postgres:16-alpine`, `127.0.0.1:15432`), i.e. the same server/image family CI uses |
| Schema | `alembic upgrade head` from an empty database ⇒ `c8f2d3e4a5b6 (head)`; conftest then skips `create_all`, exactly as in CI |
| URL | `postgresql+psycopg://…@127.0.0.1:15432/gi_qa_pg_lane_6a42` (credentials read from the container env, never printed) |
| Command | `./.venv/Scripts/python.exe -m pytest tests -q` |

| Lane | Result | Exit | Duration |
|---|---|---|---|
| SQLite (in-memory, `StaticPool`) | `1764 passed, 1 skipped` | 0 | 458.97 s |
| PostgreSQL (disposable DB, Alembic head) | `1765 passed, 0 skipped, 0 failed` | 0 | 1175.92 s |

Parity: **no test fails on either backend**, and the only difference is the single skip, which is expected and correctly backend-gated:

```
no tests collected (1765 deselected) under -m pg   # the «pg» marker is not used by any test
```

So the SQLite skip is not marker-driven; it is the explicit dialect guard in `tests/test_dispatch.py:173` — `@pytest.mark.skipif(_dialect() == "sqlite", reason="needs two real row locks; SQLite shares one in-memory connection")`. On PostgreSQL that test executes and passes, which is exactly the `+1 passed / −1 skipped` difference. The suite is therefore byte-for-byte consistent across backends, and the new guard file (`tests/test_ui_page_wiring.py`) is backend-agnostic (it reads `backend/static/index.html` and shells out to Node, so it neither touches the database nor depends on the dialect).

Primary database safety: nothing in either lane pointed at `globalintelligence`. Verified after the run — the primary DB still has 53 tables at `alembic_version = c8f2d3e4a5b6`, and `gi_qa_pg_lane_6a42` no longer exists (`SELECT count(*) ... = 0`). Log file removed.

**Timing note:** the PG lane is ~2.6× slower here (1176 s vs 459 s) because `NullPool` opens a fresh connection per session and `_clean_tables` issues 53 `DELETE`s per test against a real server. This is a local measurement, not a CI budget.

---

## 12. Python 3.12 + pytest<9 CI-Equivalent Lane

`backend/requirements-dev.txt` pins `pytest>=8.0,<9` and CI pins Python `3.12`; the local default interpreter was Python 3.14.4. A throwaway interpreter was provisioned with `uv` to remove that gap.

### 12.1 Environment (matching `.github/workflows/ci.yml` `backend` job)

| Item | Value |
|---|---|
| Interpreter | Python **3.12.15** (`uv python install 3.12`; first download attempt failed with a truncated archive, second attempt succeeded in 7m01s) |
| pytest | **8.4.2** (satisfies the CI pin `>=8.0,<9`) |
| ruff | 0.17.4 (CI pin `>=0.5,<1`) |
| Database | disposable `gi_qa_pg312` on `gi_postgres` (postgres:16-alpine) |
| Env vars | `DATABASE_URL` (pg), `MOCK_MODE=true`, `APP_ENV=development`, `API_KEY=""`, `APP_ENCRYPTION_KEY` = the public dummy from `ci.yml` |
| Command | `pytest tests -q --basetemp=.pytest-ci` (exactly as CI) |

### 12.2 Migration steps of the CI job, reproduced

```
alembic upgrade head        -> exit 0
alembic downgrade base      -> exit 0
alembic upgrade head        -> exit 0
alembic heads               -> c8f2d3e4a5b6 (head)     # single head, as CI requires
```

Final schema on the disposable DB: 53 tables at `c8f2d3e4a5b6`.

### 12.3 Suite result and cross-version comparison

| Lane | Python | pytest | Result | Exit | Duration |
|---|---|---|---|---|---|
| PostgreSQL | 3.14.4 | 8.4.2 | `1765 passed, 0 skipped` | 0 | 1175.92 s |
| PostgreSQL | **3.12.15** | **8.4.2** | `1765 passed, 1 warning` | **0** | 1465.25 s |
| SQLite | 3.14.4 | 8.4.2 | `1764 passed, 1 skipped` | 0 | 458.97 s |

**No version-specific test failures.** Same 1765 tests, same outcome on Python 3.12 and 3.14; the only observable difference is the warning count (`697` → `1`), which is expected: the 697 warnings on 3.14 are `asyncio.get_event_loop_policy` / `set_event_loop_policy` `DeprecationWarning`s emitted by `pytest-asyncio` under Python 3.14, plus the interpreter-level `Task.current_task` deprecations. None of them exist on 3.12, and none is a failure. The 3.12 lane was ~25% slower (1465 s vs 1176 s) on the same machine and database.

### 12.4 Finding F20 — the CI `Lint (ruff)` step fails (not version-specific)

`ruff check backend domains tests scripts source_bot` — the exact CI command — exits **1**:

```
domains/events/actor_extraction.py:35:23 B033   duplicate item "may" in a set
domains/events/actor_extraction.py:62:50 B033   duplicate item "athens" in a set
domains/events/actor_extraction.py:148:5 I001   import block unsorted
domains/events/extractor.py:10:1       I001   import block unsorted
domains/events/extractor.py:29:45      F401   extract_actors_deterministic imported but unused
domains/events/extractor.py:374:5      F841   local variable used_ai assigned but never used
domains/events/extractor.py:397:49     F811   extract_actors_deterministic redefined
tests/test_actor_extraction.py:73:9    I001
tests/test_actor_extraction.py:99:5    I001
tests/test_actor_extraction.py:129:5   I001
tests/test_actor_extraction.py:172:30   UP031  percent-format used
```

Scope and provenance:

- All 11 findings are in the three **uncommitted** files of the actor-extraction work (`domains/events/actor_extraction.py`, `domains/events/extractor.py`, `tests/test_actor_extraction.py`) — they are **not** in `backend/static/index.html` or `tests/test_ui_page_wiring.py`, so this stage added no lint debt.
- **Not version-specific:** ruff 0.17.3 (main venv) and ruff 0.17.4 (3.12 venv) report an identical finding set (8 unique file+rule pairs), so upgrading or downgrading the linter does not change the outcome.
- **Two findings need a human decision, not an autofix:** `B033` duplicates (`"may"`, `"athens"`) inside set literals mean a term is silently dropped at parse time — the intent was probably two different strings (e.g. a casing or suffix variant). `F811`/`F401` on `extract_actors_deterministic` means the module-level import at line 29 is shadowed by a later definition, so the import is dead.
- Consequence: the `backend` CI job would stop at the lint step before ever running the suite, so **remote CI parity is still unproven (F11 remains NOT_RUN)** — and this is now the cheapest known blocker to clear.

### 12.5 Not reproduced locally

- The `docker` job (image builds), the `e2e` job (Playwright full stack) and the `frontend` job (`npm run lint/typecheck/build`) — none was run for this lane.
- The `backend-sqlite` job (`pytest ../tests -q -m "not pg"` from `backend/`) under 3.12 — the SQLite lane was measured on 3.14 only (§10).

### 12.6 Cleanup

`gi_qa_pg312` dropped (`count = 0`), `.pytest-ci` basetemp and every temporary log removed, and the throwaway `.venv312` deleted (`.gitignore` only covers `.venv/` and `venv/`, so it would otherwise show up as untracked). Recreating it takes ~9 minutes: `uv python install 3.12 && uv venv --python 3.12 .venv312 && uv pip install --python .venv312/Scripts/python.exe -r backend/requirements-dev.txt`. Primary DB untouched: 53 tables at `c8f2d3e4a5b6`.

### 12.7 Lint gate cleared (closes §12.4)

All 11 findings of §12.4 were fixed; the exact CI command now passes:

```
ruff check backend domains tests scripts source_bot   ->  All checks passed!  (exit 0)
```

What was changed and why:

| Finding | Change | Real bug? |
|---|---|---|
| `B033` `"may"` (×2 in `_NON_ACTOR_WORDS`) | Removed the copy from the modal-verb run; the month run still carries `"may"` | **No** — both copies were the same lowercase token, and `_is_valid_actor` lowercases the candidate, so filtering is unchanged. One entry is enough and the duplicate only invited the reader to believe two meanings were encoded |
| `B033` `"athens"` (×2 in `_LOCATION_WORDS`) | Removed the trailing duplicate after `"usa"` | **No** — same-token duplicate; the first entry already filters Athens |
| `F401` + `F811` `extract_actors_deterministic` in `extractor.py` | Deleted the shadowing re-import inside `_resolve_actors`; the module-level import is now the single source and is actually used | **Yes, latent** — two import sites for one symbol meant a future edit to the module-level import could silently be ignored on the fallback path |
| `F841` `used_ai` in `extractor.py` | Removed the dead assignment; the branch already tests `ai_list` directly | **No** — dead store |
| `I001` ×5 | Import blocks sorted (`ruff check --fix` for the test file; manual reordering for the `sqlalchemy`/first-party split and the `domains.events.*` block) | **No** |
| `UP031` in `test_actor_extraction.py` | `"...%r" % actors` → `f"...{actors!r}"` | **No** |

Behavioral parity was checked rather than assumed: `"may" in _NON_ACTOR_WORDS` and `"athens" in _LOCATION_WORDS` are both still `True` after the dedupe (202 non-actor words, 48 location words).

Verification of the touched code: `pytest tests/test_actor_extraction.py tests/test_events.py tests/test_ai_extraction_validation.py tests/test_mock_provenance.py tests/test_domain_routing_refresh.py -q` ⇒ **48 passed**, exit 0.

The full suite was re-run after these edits — see §12.8. The CI `Lint (ruff)` step is now executable, so remote CI is blocked only on actually being triggered (**F11 still NOT_RUN**).

### 12.8 Post-lint full-suite baseline (current code)

The green baseline now covers the edited code, not just the pre-edit tree:

| Item | Value |
|---|---|
| Database | fresh disposable `gi_qa_pg_post_lint` on `gi_postgres`, migrated from empty |
| Migrations | `alembic upgrade head` ⇒ exit 0, single head `c8f2d3e4a5b6` |
| Command | `pytest tests -q --basetemp=.pytest-ci` with the CI env vars (`DATABASE_URL`, `MOCK_MODE=true`, `APP_ENV=development`, `API_KEY=""`, `APP_ENCRYPTION_KEY`) |
| Result | **`1765 passed, 0 failed, 0 skipped`**, 697 warnings, **exit 0** |
| Duration | 1414.65 s (0:23:34) — same machine and DB as §11's 1175.92 s, so the extra ~4 minutes is host load, not test behavior |

Same 1765-test count and same outcome as the pre-edit PostgreSQL lane, so the lint fixes changed no runtime behavior — consistent with the parity checks in §12.7. Cleanup: `gi_qa_pg_post_lint` dropped, basetemp and logs removed; primary DB untouched (53 tables at `c8f2d3e4a5b6`).

---

## 13. Geopolitics Actor Backfill — Prepared (No-Key Validation)

The backfill was **prepared but not executed**. A real AI provider key is available in this environment (groq), but the stage scope was explicitly limited to validating everything that does not need the key, so no AI calls were made and the primary DB was not written to.

### 13.1 Tool

`domains/geopolitics/backfill_actors.py` — CLI (`python -m domains.geopolitics.backfill_actors`):

| Flag | Meaning |
|---|---|
| (default) | dry-run, no writes, no AI |
| `--apply` | apply changes (refuses to run unless a real provider is configured) |
| `--limit N` | process at most N empty-actor events (0 = all) |
| `--force` | reprocess events that already have actors |
| `--analyze` | run `GeopoliticalEngine.analyze_all()` after apply |
| `--period YYYY-MM` | period for analysis (default: current month) |
| `--json` | machine-readable summary |

Design:
- Dry-run reports counts and a **deterministic preview** (labelled "preview, not trusted") without any writes.
- `--apply` requires `effective_mock_mode() == False` and `ai_default_provider != mock`; otherwise exits 2 with a clear message.
- For each event with empty actors (or all events under `--force`), gathers linked articles, calls the AI extraction path (`EXTRACT_EVENT` + `_resolve_actors` with `allow_create=True`), updates `Event.actors` and merges `actor_resolution`/`actor_backfill` into `event_metadata`, and links entities.
- Idempotent: only events with empty actors are processed unless `--force`.
- Tracks entity count before/after.

### 13.2 No-key validation results (primary DB, read-only)

| Check | Result |
|---|---|
| Schema (`events`, `articles`, `geopolitical_assessments`) | OK |
| Provider availability | available (`ai_default_provider=groq`) |
| Total events | 708 |
| Events with empty actors | 708 (100%) |
| Events with actors | 0 |
| Events with no linked articles | 0 (all 708 are backfillable) |
| Deterministic preview | 105 events / 145 candidates (preview, not trusted) |
| Refusal in mock mode (`MOCK_MODE=true --apply`) | exits 2, `provider_available=false` |
| ruff | clean |

### 13.3 What still needs the key (not validated)

- The actual AI extraction + entity creation on real events (`--apply`). One smoke run on a disposable DB with `--limit 1` would prove the write path end-to-end; deferred to avoid spending provider credits and to keep the primary DB untouched.
- `--analyze` producing `GeopoliticalAssessment` rows from the newly populated actors.

### 13.4 Usage when ready

```
# dry-run preview (no writes, no AI):
python -m domains.geopolitics.backfill_actors

# apply to all empty-actor events then analyze:
python -m domains.geopolitics.backfill_actors --apply --analyze

# bounded smoke test on a throwaway DB (recommended first):
DATABASE_URL=postgresql+psycopg://.../gi_throwaway python -m domains.geopolitics.backfill_actors --apply --limit 1 --json
```

Primary DB untouched by this stage: 53 tables at `c8f2d3e4a5b6`.
