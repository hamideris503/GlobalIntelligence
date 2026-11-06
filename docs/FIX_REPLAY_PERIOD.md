# Replay drift fix — rerun pinned to the stored period

**Type:** defect fix (no new stage id)
**Status:** `VERIFIED`
**Trigger:** the full suite was red with exactly one failure:
`tests/test_audit.py::test_replay_all_supported_engines_match` (`engine=risk`, `match=False`, `rows=6`).

## 1. Root cause (not a flaky test)

`domains/audit/replay.py:rerun()` called the period-keyed engines **without a period**:

```python
RiskEngine(db).analyze_all()          # period defaults to the current month
GeopoliticalEngine(db).analyze_all()
SocialEngine(db).analyze_all()
PerformanceEngine(db).record()
```

Every one of those engines is genuinely idempotent (`UniqueConstraint(category/actor/scope/model,
period)` + upsert), so the duplicate-row theory was wrong. The drift came from the **period**:
the test seeds and runs `period="2026-10"`, then `replay()` re-ran with the default `datetime.now()`
period, which on 2026-11-02 is `2026-11`. The rerun therefore inserted a new month's assessments and
the fingerprint (which includes `period`) changed — `before=3 rows` became `after=6 rows`.

This is a defect in `replay`, not only in the test: `POST /api/audit/replay` would report drift on the
first day of every month even when the engines are perfectly deterministic, and a replay of an older
period would silently write rows for the current one.

## 2. Change

`domains/audit/replay.py`:

- new `latest_period(db, engine)` → newest `period` already stored for `risk`, `geopolitics`,
  `society`, `performance` (returns `None` for `macro`, which is not period-keyed at this level, and
  when the table is empty);
- `rerun()` resolves that period once and passes it to the engine (`analyze_all(period=…)` /
  `record(period=…)`).

No assertion was relaxed, no engine logic changed, no migration, no dependency.

## 3. Evidence

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | All checks passed |
| Replay suites | `pytest tests/test_audit.py tests/test_replay_period.py tests/test_risk.py tests/test_geopolitics.py tests/test_society.py tests/test_performance.py -q` | **40 passed** |
| Replay + audit only | `pytest tests/test_audit.py tests/test_replay_period.py -q` | 11 passed |
| Full suite | `pytest tests -q` | see the run recorded in the stage report |

New regression tests (`tests/test_replay_period.py`):

1. seed a snapshot, run `RiskEngine` for `2025-01`, then `replay("risk")` → `match is True`,
   `rows` unchanged, and **no** row exists for the current calendar month;
2. with an empty database `latest_period` is `None` and replay skips honestly without writing rows.

## 4. Remaining caveat

If the clock crosses a month boundary between the original run and the replay, the replay will pin the
stored period (correct) but a *new* run in that window would still create the new month's rows — that is
expected engine behaviour, not drift, and the fingerprint is taken around the rerun only.
