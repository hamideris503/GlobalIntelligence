# F03.0 — Configuration Control Plane (backend)

**Stage:** `F03.0`
**Status:** `VERIFIED` (code + tests + migration SQL). Runtime revision pinning (2.7) is **not** part of
this stage and is listed as a gap below.
**Scope source:** `docs/DELTA_IMPLEMENTATION_INVENTORY.md` rows `2.1`, `2.2`, `2.4`, `2.5`, `2.6`
(the delta spec file itself is not present in this checkout).

---

## 1. Before

| Requirement | State before this stage |
|---|---|
| 2.1 shared configuration descriptor contract | `MISSING` — no `/api/configuration/*`, zero hits for `ConfigurationRevision` |
| 2.2 revisions + rollback + audit + optimistic locking | `MISSING` — `PATCH /api/sources/{id}` mutates the row in place |
| 2.4 adapter registry as single source of truth | `PARTIAL` — `source_bot/registry.py` picks adapters, but no descriptor endpoint and no public adapter list |
| 2.5 draft → validate → test → preview → enable | `MISSING` — `POST /api/sources` writes an active row immediately |
| 2.6 preview that never ingests | `MISSING` — the UI "trial fetch" calls `POST /api/ingest` with `limit: 5`, which ingests |

## 2. What was added

| File | Purpose |
|---|---|
| `backend/configuration/errors.py` | `ConfigurationError` with `status_code` (404 / 409 / 422) |
| `backend/configuration/descriptors.py` | descriptor contract + deterministic validation; adapter list and adapter choice come from `source_bot.registry` |
| `backend/configuration/preview.py` | non-ingesting preview: `connection_check` (SSRF/DNS policy) → adapter fetch → sanitized samples |
| `backend/configuration/service.py` | revision lifecycle, optimistic locking, activation, append-only rollback, audit |
| `backend/database/models/configuration.py` | `ConfigurationInstance`, `ConfigurationRevision` |
| `db/migrations/versions/a7f3c9d1e2b4_phase60_configuration_control_plane.py` | tables, indexes, unique constraints (`down_revision = f16c3d4e5f6a`) |
| `backend/api/schemas/configuration.py`, `backend/api/routers/configuration.py` | HTTP surface under `/api/configuration` |
| `tests/test_configuration_control_plane.py` | 12 tests through `TestClient` (router wiring included) |

`source_bot/registry.py` gained two constants only: `ADAPTERS` and `PREVIEW_ADAPTERS`. The adapter
selection logic (`pick_adapter`) was **not** duplicated — validation and preview both call it.

## 3. Contract

`GET /api/configuration/definitions` returns, per kind, the fields with `kind` (`text|url|bool|enum|json`),
`required`, `choices`, `max_length`, `secret`, plus `adapters` / `preview_adapters` / `version`.

Validation is deterministic and network-free (`descriptors.validate`):

1. unknown fields are rejected (no silent drop),
2. required / type / enum / length checks per field,
3. `url` fields go through `source_bot.security.validate_url` (scheme, userinfo, private host/IP),
4. the endpoint is resolved by `pick_adapter`; adapter `skip` becomes issue `no_usable_endpoint`,
5. `endpoint_config.api_key_env` must be an env-var **name**; key-looking values are rejected (`secret_value`).

## 4. Lifecycle rules

```
draft ──validate──> validated ──test──> tested ──activate──> active ──> archived
  ^                    │                 │
  └── issues ──────────┘                 └── preview failure keeps evidence, status stays validated
```

- `latest_revision` is the instance version: every write sends `expected_revision`; a mismatch returns
  **409** (optimistic locking).
- `active` and `archived` revisions are immutable (409 on re-validate).
- Activation requires `tested`; activating a new revision archives the previous one.
- History is append-only: rollback creates a **new** revision whose payload is a copy of the target,
  re-runs deterministic validation, records `network_test_skipped: true`, and activates it.
- Every activation and rollback writes an `AuditRecord` (`configuration_activate` / `configuration_rollback`).

## 5. Preview never ingests

`preview_fetch` writes nothing: no `Document`, no ingestion counter, no raw payload. It returns
`{adapter, url_origin, count, samples[], ingested: false}` where each sample carries a truncated title,
a truncated summary, `content_chars` and a `sha256` prefix of the body. `url_origin` is
`scheme://host[:port]`, so query-string tokens never reach the response. Adapters without a preview path
(`csv`, `xml`, `html`, `rest_json`, `specialized`) answer honestly with `422 unsupported_adapter` instead of
pretending to have fetched.

## 6. Verification

| Check | Command | Result |
|---|---|---|
| Lint (whole repo scope) | `ruff check backend domains tests scripts source_bot` | **All checks passed!** |
| Stage tests | `python -m pytest tests/test_configuration_control_plane.py -q` | **12 passed** |
| Migration SQL (PostgreSQL dialect, offline) | `alembic upgrade f16c3d4e5f6a:a7f3c9d1e2b4 --sql` | exit 0; creates both tables, 2 indexes, 2 unique constraints, FK `ON DELETE CASCADE`, bumps `alembic_version` |
| Live DB head matches the new `down_revision` | `GET /health/db` | `migration: f16c3d4e5f6a` — the new revision applies on top of the exact live head |
| Full suite (whole repo) | `python -m pytest tests -q` | **1 failed, 1524 passed, 1 skipped** (374s) |

The single failure is `tests/test_audit.py::test_replay_all_supported_engines_match` (`engine=risk`
`match=False`, `rows=6`). It is **not** caused by this stage: the risk replay path
(`domains/audit/replay.py`, `domains/risk/*`, `tests/test_audit.py`) is untouched (`git status` is clean
for those files) and the failure reproduces when only `tests/test_audit.py -k replay` is selected, i.e.
without any configuration test in the process. The new tables are not part of that engine's fingerprint.

Test coverage in that file: descriptor↔registry equality, unknown kind/instance 404, revision numbering,
stale-`expected_revision` 409, validation issues (`no_usable_endpoint`, `unsafe_url`, `unknown_field`),
`test` before `validate` 409, no-ingest assertion (document count unchanged), activate-before-test 409,
active-immutability 409, archive of the previous active revision, audit record presence, rollback
creating revision 3 with `network_test_skipped`, preview rejecting private URLs, unsupported adapter,
URL policy, and sanitization (no `SECRET` query token, truncated fields).

## 7. Known gaps

| Severity | Gap |
|---|---|
| — | Requirement 2.7 (runtime pins the config revision per run) is now implemented — see `docs/F03_CONFIG_PINNING.md`. `run_source()` resolves the plan from the active revision and records it per source in the job result; sources without an instance keep the live row. |
| `MEDIUM` | No frontend surface: `/api/configuration/*` is backend-only, as F03.0 requires; the Sources wizard (3.2) consumes it later. |
| `MEDIUM` | `Source` rows are not yet driven by an active configuration revision — creating an instance does not create or update a `Source`. That wiring belongs with the wizard/descriptor stage and avoids changing ingestion behaviour here. |
| `LOW` | The full Alembic chain cannot run on SQLite in this checkout (pre-existing `ALTER` constraint in an older migration aborts before this revision); CI runs Alembic on PostgreSQL only, which is what the offline render above verifies. |

**Next stage:** `F12.1.1` per the inventory, unless the owner prioritises 2.7 (runtime revision pinning)
or the Sources wizard (2.5/3.2 UI) first.
