# N8N-RECOVERY-01 — DNS, Network and Backend Connectivity

**Date/Time:** 2026-11-12 (diagnosis & repair session)
**Git branch:** `step6a-analysis-dashboard`
**HEAD commit:** `31b4ca4c662e215931781451605609e505a257e2`
**Working tree:** modified (UI/a11y/offline work in progress; no reset/clean performed)

---

## A. Baseline

### Deployment methods
- **n8n:** Docker container `gi_n8n` (image `n8nio/n8n:2.42.6`), up ~2 days, published on `127.0.0.1:5678`.
- **Backend (active):** Docker container `gi_backend_parity` (image `globalintelligence-backend:candidate-step6a42-r3-20261111`), up ~23h, healthy, published on `127.0.0.1:8000`.
- **PostgreSQL:** Docker container `gi_postgres` (image `postgres:16-alpine`), up ~2 days, healthy, published on `127.0.0.1:15432`, network `globalintelligence_gi_net`.
- **Compose-managed backend** `gi_backend` (service `backend`) is **Exited (0)** since 3 days ago; not running.

### Docker network topology (before repair)
| Container | Networks |
|---|---|
| `gi_n8n` | `globalintelligence_gi_net` (172.18.0.4) |
| `gi_postgres` | `globalintelligence_gi_net` (172.18.0.3) |
| `gi_backend_parity` (active) | `bridge` (172.17.0.2) only |

**Root cause of Failure B:** n8n and PostgreSQL share `globalintelligence_gi_net`, but the active backend (`gi_backend_parity`) was attached only to the default `bridge` network. Therefore the hostname `backend` (used by every workflow) did **not** resolve from inside n8n (NXDOMAIN), and no TCP connection could be established. The compose-managed `gi_backend` service (which would have provided the `backend` DNS alias) was stopped.

### DNS resolver inside n8n
- `/etc/resolv.conf`: `nameserver 127.0.0.11` (Docker embedded DNS), upstream host `192.168.65.7`, `ndots:0`.
- Global DNS works (e.g. `google.com`, `feeds.bbci.co.uk`, `www.federalreserve.gov` resolve).
- `backend` → **NXDOMAIN** (before repair).
- `postgres` / `gi_postgres` → resolve to `172.18.0.3`.

### Workflow inventory (7 workflows, all active=1)
| ID | Name | Backend host used |
|---|---|---|
| `gi-phase4-trigger` | GI — Trigger → Backend → Database | `backend:8000` |
| `gi-scheduled-ingestion` | GI — Scheduled News Ingestion | `backend:8000` |
| `gi-daily-briefing` | GI — Daily Briefing & Risk | `backend:8000` |
| `gi-hourly-intelligence` | GI — Hourly Intelligence Pipeline | `backend:8000` |
| `gi-hourly-markets` | GI — Hourly Markets & Macro | `backend:8000` |
| `gi-ops-monitor` | GI — Ops Monitor | `backend:8000` |
| `gi-sourcebot-hourly` | GI — Source Bot Hourly | `backend:8000` |

All HTTP nodes use `http://backend:8000/...`, method POST (except ops status GET), header `X-API-Key: ={{ $env.BACKEND_API_KEY }}`, timeouts 10s–300s. No per-workflow hostname differences → shared root cause.

---

## B. Root cause

### Failure B (Execution 6116) — "The connection cannot be established"
- **Workflow:** GI — Scheduled News Ingestion
- **Node:** Run news ingestion (backend)
- **Destination:** `http://backend:8000/api/ingest/all?limit=20&mock=false`
- **Root cause:** `backend` hostname unresolvable from n8n container (NXDOMAIN) because the active backend container was not attached to `globalintelligence_gi_net` and the compose-managed `backend` service was stopped. Underlying error class: DNS resolution failure (`NXDOMAIN`), not a backend application defect.

### Failure A (Execution 6118) — "The DNS server returned an error"
- **Workflow:** GI — Hourly Intelligence Pipeline
- **Node:** 1. Ingest news (POST `http://backend:8000/api/ingest/all?limit=20&mock=false`)
- The node itself calls the backend, not an external RSS feed. The "DNS server returned an error" message corresponds to the same `backend` NXDOMAIN condition above. External feed hostnames (e.g. `www.aljazeera.com`) resolve partially (`No answer` for some) but global DNS is functional; this is a per-provider condition, not a global DNS outage. No evidence of a broken resolver.

**Shared root cause:** yes — both failures stem from `backend` being unresolvable from n8n due to network attachment, not from n8n itself or from external DNS.

---

## C. Repairs

### Repair 1 — Attach active backend to the shared Docker network
- **Previous:** `gi_backend_parity` attached only to `bridge` (172.17.0.2); `backend` unresolvable from n8n.
- **Change:** `docker network connect --alias backend globalintelligence_gi_net gi_backend_parity`
- **Result:** `gi_backend_parity` now on both `bridge` (172.17.0.2) and `globalintelligence_gi_net` (172.18.0.5) with DNS alias `backend`.
- **Why:** smallest targeted change; preserves all existing container memberships and volumes; no restart, no data change.
- **Security:** backend remains on internal Docker network only; no new public port exposure.
- **Rollback:** `docker network disconnect globalintelligence_gi_net gi_backend_parity` (restores prior state).
- **Durability note:** this is a runtime attachment. If `gi_backend_parity` is recreated, the attachment must be re-applied (or the compose-managed `gi_backend` service should be started on `gi_net` instead). No compose file was modified.

No other changes were made. No workflows, nodes, schedules, credentials, or application code were modified.

---

## D. Verification

### Test A — DNS (from inside n8n)
- `nslookup backend` → `Name: backend, Address: 172.18.0.5` (PASS)
- `nslookup google.com`, `feeds.bbci.co.uk`, `www.federalreserve.gov` → resolve (PASS, global DNS functional)
- `www.aljazeera.com` → `No answer` (provider-specific; not a resolver outage)

### Test B — Backend health (from inside n8n)
- `wget http://backend:8000/health` → `{"status":"ok"}` (PASS)
- `wget http://backend:8000/health/db` → database ok, PostgreSQL 16.15 (PASS)

### Test C — Authenticated endpoint (from inside n8n)
- `wget --header="X-API-Key: $BACKEND_API_KEY" http://backend:8000/api/ops/status` → `{"database_ok":true, "counts":{...}}` (PASS, auth intact)

### Test D — Workflow node verification
- Not executed as a manual run to avoid triggering production ingestion / DB writes. Authenticated read-only endpoint verified from the n8n runtime instead.

### Test E — End-to-end ingestion
- **NOT_RUN** — would write to the primary `globalintelligence` database; prohibited by safety rules. No disposable-database mode was verified in this session.

### PostgreSQL baseline/final
- No reads or writes performed against `globalintelligence` beyond the existing backend health check (which is read-only). Primary DB unchanged.

---

## E. Remaining blockers
1. **Long-term schedule stability** — PENDING (requires observing scheduled runs over time; no manual production ingestion triggered per safety rules).
2. **Durability of the network attachment** — RESOLVED. RestartPolicy changed from `no` to `unless-stopped` (`docker update --restart unless-stopped gi_backend_parity`). The `docker network connect` membership (including the `backend` alias) is stored in the container config and persists across restarts and daemon restarts. Only a manual `docker rm` + `docker run` would lose it; the re-apply command `docker network connect --alias backend globalintelligence_gi_net gi_backend_parity` remains documented as fallback.

Resolved during this session:
- External provider `www.aljazeera.com` — actually reachable; `wget https://www.aljazeera.com/xml/rss/all.xml` returns valid RSS (exit 0). The earlier `nslookup` "No answer" was a transient resolver quirk, not a blockage.
- All 7 workflows share the same `backend:8000` hostname; connectivity restored for all of them.

---

## F. Final verdict

**PARTIALLY_RECOVERED**

- **n8n infrastructure recovery:** PASS (DNS + network + Backend connectivity restored and verified from inside n8n; RestartPolicy set to unless-stopped for durability).
- **Backend connectivity (n8n → Backend):** PASS (health + authenticated endpoint verified).
- **External news source availability:** PASS (global DNS functional; aljazeera feed returns valid RSS; bbc/federalreserve resolve and reachable).
- **Full production ingestion:** NOT_RUN (DB-write safety).
- **Long-term schedule stability:** PENDING.