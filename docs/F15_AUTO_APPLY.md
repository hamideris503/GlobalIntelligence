# F-15 — automatic adaptive-routing application at startup

**Item:** `F-15` ("AdaptiveRouter has no production consumer", `docs/BASELINE_F00.md:118`)
**Status:** `VERIFIED` for the automatic-apply half. The router already had an API and a CLI; what was
missing — `docs/F15_ADAPTIVE_ROUTER.md:29-31` — was code that applies the chain by itself.

## 1. Before

| Piece | State |
|---|---|
| `AdaptiveRouter` (`domains/ai_routing/router.py`) | records stats, suggests a chain, builds `Route` objects |
| consumers | `GET/POST /api/ai-routing/*` and `python -m domains.ai_routing.run_routes` — both **manual** |
| startup (`backend/main.py` lifespan) | wired credentials, ingest recovery, dispatch recovery — nothing for AI routing |

So a fresh deployment with recorded statistics still used the static provider order until an operator
called `/api/ai-routing/apply`.

## 2. Change

| File | Change |
|---|---|
| `backend/core/config.py` | `adaptive_routing_enabled: bool = False`, `adaptive_routing_tasks: str = "classify_article,extract_relations"` |
| `backend/ai/adaptive_bootstrap.py` | `parse_tasks()` (CSV → unique list, defaults when empty), `build_effective_routes()`, `apply_adaptive_routes()` |
| `backend/main.py` | in `lifespan`, when the flag is on: build routes from the DB and `set_routes` on the gateway |

Design rules that keep this safe:

1. **Off by default.** With `ADAPTIVE_ROUTING_ENABLED` unset the gateway behaves exactly as before —
   nothing is applied, no extra query runs, no behaviour change in tests or in mock mode.
2. **Evidence only.** `build_effective_routes()` drops any task whose suggestion is empty, so a task
   with no recorded runs keeps the static chain instead of receiving an empty provider list (which
   would have made every call for that task fail).
3. **No new scoring.** The Laplace-smoothed ordering, static-order fallback and `Route` construction
   all come from the existing `AdaptiveRouter`; the bootstrap only decides *when* to apply.
4. **Startup must not break.** The whole block is wrapped like the ingest/dispatch recoveries: a
   missing DB or migration logs a warning and the server still starts (`/health` resilience rule).

## 3. Enabling it

```bash
ADAPTIVE_ROUTING_ENABLED=true
ADAPTIVE_ROUTING_TASKS=classify_article,extract_relations   # optional; this is the default
```

Runtime re-apply remains available as before: `POST /api/ai-routing/apply?tasks=…`.

## 4. Verification

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | All checks passed |
| Targeted suites | `pytest tests/test_adaptive_bootstrap.py tests/test_ai_routing.py tests/test_ai_gateway.py tests/test_security.py -q` | **43 passed** |

`tests/test_adaptive_bootstrap.py` covers: flag off by default; `parse_tasks` trims/dedupes/defaults;
tasks without statistics are excluded; applying injects the scored chain into the gateway while an
unknown task keeps its static chain; and with no statistics at all `apply_adaptive_routes` returns `{}`
and never calls `set_routes`.

## 5. Remaining limits

| Severity | Gap |
|---|---|
| `MEDIUM` | Application happens **once at startup**; new statistics are picked up on the next start or via `POST /api/ai-routing/apply`. A periodic refresh is a separate decision (interval, drift, who owns it). |
| `LOW` | `set_routes` replaces the whole route map, so the bootstrap applies only the tasks it built. At startup the map is empty, which is exactly the intended case; calling the bootstrap later would drop routes it did not rebuild. |
