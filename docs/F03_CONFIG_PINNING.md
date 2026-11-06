# 2.7 — Runtime pins the configuration revision per ingestion run

**Requirement:** `docs/DELTA_IMPLEMENTATION_INVENTORY.md` row `2.7` — "Runtime pins the config revision
per run" (`MISSING`: "No revision field on `Source`/`Job`; `source_bot/runner.py` resolves adapters live.")
**Status:** `VERIFIED` — the pin has runtime effect, not just a stored column.

## 1. Design choice

The Control Plane (F03.0) stores configuration as `ConfigurationInstance(kind, slug)` +
append-only `ConfigurationRevision`. A source is addressed as `kind="source", slug=<Source.name>`
(`Source.name` is unique, so no new column is needed on `Source`).

- **With an active revision:** the run uses the revision's payload — that payload decides the adapter,
  URL and `endpoint_config` through the *same* `pick_adapter` used everywhere else.
- **Without one:** the live `Source` row is used exactly as before, and no revision is reported.
- **Unusable pin** (payload resolves to `skip`, or the revision is not `active`): fall back to the live
  row and report `config_revision: null`, so ingestion never dies on a half-written draft.
- **DB/table unavailable:** the lookup logs a warning and the run continues on the live row.

## 2. What changed

| File | Change |
|---|---|
| `backend/configuration/runtime.py` (new) | `pinned_payload()` (revision number + payload of the instance's active revision), `plan_from_payload()`, `resolve_source_plan()` → `(SourcePlan, revision_or_None)` |
| `source_bot/runner.py` | `run_source()` now calls `resolve_source_plan(db, source)` instead of `pick_adapter(source)` directly, and records the pinned revision on the per-source metrics |
| `source_bot/metrics.py` | `SourceMetrics.config_revision` (+ `as_dict()`), so every run result carries which revision each source ran on |
| `tests/test_config_revision_pin.py` | 5 tests |

Because `jobs.run_job()` stores `metrics.as_dict()` in `JobRun.payload["result"]`, each ingestion job now
contains the pinned revision per source (`result.by_source.<name>.config_revision`) — the per-run pin
record required by 2.7, with **no migration** and no new table.

## 3. Verification

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | All checks passed |
| Pin tests | `pytest tests/test_config_revision_pin.py -q` | **5 passed** |
| Control plane + adaptive | `pytest tests/test_config_revision_pin.py tests/test_configuration_control_plane.py tests/test_adaptive_bootstrap.py -q` | **22 passed** |
| Ingestion suites | `pytest tests/test_source_bot_integration.py tests/test_source_bot_phase5.py tests/test_ingest_jobs.py -q` | **60 passed** |
| Full suite | `pytest tests -q` | see the run quoted in the stage report |

`tests/test_config_revision_pin.py` covers: pinned revision overrides the live row (adapter + URL come
from the payload, revision number reported); no pin → live row and `None`; an `archived` revision is not
pinned; an unusable pinned payload falls back to the live row; and a real `run_source()` call fetches the
**pinned** URL while `metrics.by_source[name].config_revision == 1` (also through `as_dict()`).

## 4. Remaining limits

| Severity | Gap |
|---|---|
| `MEDIUM` | Pinning is read-only at runtime: it does not copy the active revision back into `Source`, and existing `Source` rows are not migrated into `ConfigurationInstance`s. A source with no instance keeps its live row — intentional, so ingestion behaviour does not change silently. |
| `LOW` | The lookup runs once per source per run (one indexed query); no cache, because a stale pin is worse than an extra query. |
| `LOW` | If a pin becomes unusable between activation and the run, the fallback is logged as a warning but not surfaced in the API; the run reports `config_revision: null` for that source, which is the honest signal. |
