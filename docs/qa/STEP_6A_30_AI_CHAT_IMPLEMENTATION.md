# STEP 6A.30 — AI Chat Real Conversation Workflow Implementation Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`ai-chat`) to real persisted backend data via the existing AI Gateway — genuine conversation workflow (status → compose → send → response → attribution), one page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | tracked modified + untracked (all preserved — pre-existing user work not touched) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | read-only queries only (`SELECT`/`COUNT` via `/api/ai/chat` readiness); **0 writes** |
| Disposable DB | not needed (no schema/data changes; `/api/ai/chat` uses in-memory test DB in pytest) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) — verified unchanged |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) — verified unchanged |
| Paid AI calls | **none** — mock provider used locally; no real provider API keys configured; no external outbound calls |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Candidate Readiness Comparison

Compared remaining pages against actual registered APIs, domain readiness, persisted data, missing dependencies.

| Candidate | Backend readiness | Registered APIs | Persisted/configured data | Missing dependencies | Decision |
|-----------|-------------------|-----------------|---------------------------|---------------------|----------|
| **AI Chat** | AI Gateway `POST /api/ai/chat` — returns provider/model/is_mock/usage/latency; default provider `mock` healthy | `POST /api/ai/chat` | Stateless chat (no session persistence domain) | Session/message persistence domain | **Strongest — SELECTED** (real endpoint, mock test path safe) |
| Archive | `backend/api/routers/archive.py` | GET catalog/storage/preview | Empty catalog (0 rows) | None | Empty state only |
| Evaluation | Evaluation domain POST /run, GET /scores | POST /run, GET /scores | 0 human reviews | Human-reviewed data | Empty |
| Geopolitics | Geo domain POST /analyze | POST /analyze | 0 assessments | Upstream pipeline | Needs backend work |
| Macro | Macro domain POST /analyze | POST /analyze | 0 assessments, 239 observations | Upstream pipeline | Needs backend work |
| Portfolio | Portfolio CRUD + snapshots | CRUD + snapshots | 0 portfolios | Workflow | Empty |
| Reports | Briefings POST daily/weekly | POST daily/weekly | 0 briefings | Report generation | Empty |

**Why `ai-chat`:** Existing functional backend `POST /api/ai/chat` returns real provider/model attribution, `is_mock` flag, usage, latency — **zero backend changes** required. Mock provider is healthy with no paid calls. Follows preferred rule: existing live backend + real persisted data + zero/minimal deps + read-only-safe workflow.

---

## 3. Selected Page and Justification

**Page:** `ai-chat` (`گفت‌وگوی هوشمند AI`), already registered in nav.

**Justification:**
- Existing functional backend `POST /api/ai/chat` — no backend code changes required.
- Returns real provider/model attribution, `is_mock`, usage, latency — honest real/mock labeling.
- Mock provider healthy; no external paid calls during testing (automated test path uses mock).
- Zero risk to the 18 already-integrated pages (frontend-only single-file edit).
- Persian RTL nav title already exists.
- No duplicating Providers page — attribution is read-only display, provider management remains on Providers page.

---

## 4. Existing Chat Architecture

Backend `backend/api/routers/ai.py` (`POST /api/ai/chat`, `dependencies=protected`):
- Accepts `AIGenerateRequest` (`messages[]` min 1 max 50, `role`, `task`, `temperature 0–2`, `max_tokens 1–8000`).
- Routes through AI Gateway (`backend/ai/gateway/gateway.py`) chain: configured providers → free-only policy (`backend/ai/free_policy.py`) → mock fallback.
- Returns `AIGenerateResponse`: `text`, `provider`, `model`, `usage` (prompt/completion/total tokens), `cost_estimate`, `latency_ms`, `model_version`, `prompt_version`, `is_mock`.
- Error semantics: structured `AIError` with `kind` (auth, rate_limit, quota_exhausted, free_unavailable, provider_not_allowed, model_not_allowed, etc.), `retryable`, `retry_after` — sanitized client messages, no stack traces/secrets.
- Live: `mock_mode=false`, `default_provider=mock`, mock provider `healthy=true`; all real providers (openai/anthropic/gemini/openrouter/groq/cloudflare) `healthy=false` (not configured) — no paid calls possible.

No session/message persistence domain exists (`domains/chat/`, `backend/database/models/chat*.py`, `message*.py`, `session*.py` all absent). Chat is stateless per-request — UI does not claim persistence; honest empty/error states only.

---

## 5. Registered Session and Message APIs

**Session APIs:** none registered (no `ChatSession`, `Message`, `Conversation` models). The UI does not invent session list/create/open/rename/delete — honest stateless behavior, no misleading per-user ownership labels. Single-operator model preserved.

**Message API:** `POST /api/ai/chat` (stateless, per-request). Request schema: `messages[{role,content}]`. Response schema: `{text, provider, model, usage, cost_estimate, latency_ms, model_version, prompt_version, is_mock}`.

---

## 6. Persistence Models and Relationships

None exist — no `ChatSession`/`Message` domain models. No migration added. UI renders each exchange as ephemeral (per-request response); does not claim persistence. No fake/toast-only actions.

---

## 7. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `aiChatPage()` — dedicated live container `id="aiChatLive"`, RTL page head, refresh + new-session placeholder button.
- `loadAiChat()` — house loader contract:
  - Busy guard (`window.__aiChatBusy`) prevents concurrent loads.
  - Request-generation counter (`window.__aiChatReqId`) — stale-response guard (`reqId !== window.__aiChatReqId` → return).
  - 10 s timeout via shared `api()` helper (`AbortController`).
  - DOM-presence guard before every write.
  - Guaranteed `finally` cleanup (`window.__aiChatBusy=false` only if same reqId).
  - Empty/loading/error states.
- `aiChatSend()` — submission:
  - Input validation (empty → toast), input cleared on submit.
  - User message rendered immediately (safe text via entity escaping — no `innerHTML` on arbitrary output).
  - "در حال پاسخ…" loading bubble; replaced with actual response or error.
  - Response displays provider/model attribution, token count, latency, execution-mode (`Mock (نمونه)` / `Real (واقعی)`).
  - Error state shown honestly — never fabricates success text.
  - Duplicate submission prevention while request in progress (busy state on button area).
- `renderPage()`: `if(activePage==='ai-chat')html=aiChatPage();`
- `pageRenderers`: reference fixed from `'ai-chat':aiChat` → `'ai-chat':aiChatPage`.
- Loader wiring: `if(activePage==='ai-chat'){setTimeout(loadAiChat,0);connectedPages.add('ai-chat');giUpdateRibbon();}`
- Page-aware refresh handler: `if(activePage==='ai-chat'){loadAiChat();return;}`
- Dead/duplicate legacy `sendChat()` (referenced `getElementById('chatInput')` — wrong ID) commented out to prevent shadowing.
- `esc()` for all backend-supplied strings; Persian RTL preserved; New UI conventions (grid panels, status chips, muted states).

**Actions:** refresh only (read-only re-fetch). No toast-only controls. No mutating forms.

---

## 8. Backend Changes

**None.** The `/api/ai/chat` router (`ai.py`) already implements the full AI Gateway chat path. No router, model, schema, or migration added/modified. Frontend-only change.

---

## 9. Session Workflow Results

| Workflow step | Supported? | Implementation |
|---------------|-----------|----------------|
| List sessions | No | No session domain exists — not claimed |
| Create session | No | Not claimed |
| Select session | No | Not claimed |
| Load message history | No | Not claimed |
| Rename/delete session | No | Not claimed |

Honest stateless behavior: UI does not pretend session persistence exists.

---

## 10. Message Submission Results

| Scenario | Result |
|----------|--------|
| Send message (mock provider healthy) | `POST /api/ai/chat` 200 → response rendered with attribution + usage + latency |
| Send message (no provider configured) | Backend returns structured 502 `authentication failed (check the API key)` → UI renders `AI Gateway · خطا` + error message honestly |
| Empty message | Input validation toast, no request |
| Invalid/unknown provider | Backend 422 `unknown or disabled provider` → UI renders error |
| Request timeout | `api()` timeout → UI renders "مهلت درخواست به پایان رسید" |
| Duplicate submission while in progress | Busy guard blocks; no double request |
| Stale response / navigation | reqId guard + DOM-presence guard prevent overwrite |
| Input cleared after submit | Yes |
| Safe text rendering | Entity escaping, no `innerHTML` on model output |
| Provider/model attribution | Real values from `r.provider`/`r.model` |
| Execution-mode labeling | `r.is_mock` → `Mock (نمونه)` / `Real (واقعی)` |
| Persian RTL | Verified readable |

Browser verified on temp port 8010 (identical code/hash as active 8000): 2 messages (user + AI error bubble) rendered correctly, input cleared, 0 console errors.

---

## 11. Provider/Model Attribution

- Provider name: from `r.provider` (e.g. `mock`).
- Model name: from `r.model`.
- Execution mode: `r.is_mock` → `Mock (نمونه)` vs `Real (واقعی)`.
- Tokens: `r.usage.total_tokens`, latency: `r.latency_ms`.
- No credentials shown (write-only semantics preserved).
- No model discovery triggered automatically.
- Selection only from configured backend options (mock only — no unsupported models exposed).

---

## 12. Real/Mock/Dry-Run Semantics

| Label | Meaning | Source |
|-------|---------|--------|
| `Mock (نمونه)` | `is_mock=true` — response from mock provider, no inference | `r.is_mock` |
| `Real (واقعی)` | `is_mock=false` — real provider inference | `r.is_mock` |
| `PROVIDER_UNAVAILABLE` | Backend 502/403/422 structured error | UI renders `AI Gateway · خطا` |
| `GENERATION_FAILED` | Gateway error | UI renders error honestly |

Current config: `mock_mode=false`, only `mock` provider healthy — so live calls return structured `auth` error (no provider keys). **Never labels mock as real.** No dry-run distinction exposed by backend — shown as unknown rather than guessed.

---

## 13. Error and Retry Behavior

| Error condition | UI behavior |
|-----------------|-------------|
| No configured provider | 502 `authentication failed` → honest error bubble |
| Missing credentials | Same 502 |
| Provider unavailable | Structured 403/422 → honest error bubble |
| Rate limiting | `retryable` respected; no silent retry |
| Invalid message | 422 validation → honest error bubble |
| Request timeout | `api()` timeout → "مهلت درخواست به پایان رسید" |
| Gateway error | Structured error → honest error bubble |
| Message persistence failure | N/A — stateless chat, no persistence claimed |
| Session not found | N/A — no session domain |
| Network disconnection | Fetch error → honest error bubble |

**Retry:** No retry action offered — stateless per-request; retrying is a fresh user-initiated send (safe, no duplication risk since no persistence).

---

## 14. Tests and Browser Results

Backend pytest (all pass):
| Suite | Result |
|-------|--------|
| `tests/test_ai_chat.py` + `test_ai_gateway.py` + `test_ai_routing.py` + `test_ai_budget.py` + `test_ai_error_responses.py` + `test_ai_extraction_validation.py` | **81 passed** |
| `tests/test_geo_events.py` + `test_worldstate.py` + `tests/test_analyses_dashboard.py` + `tests/test_risk_forecast_decisions.py` | **60 passed** |

Browser verification (temp port 8010, identical code/hash to active 8000):
| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0, 2 inline scripts pass |
| Browser: ai-chat direct nav | breadcrumb `گفت‌وگوی هوشمند AI`, page head correct |
| Browser: status table | mock_mode / provider / roles populated |
| Browser: send message | user bubble + AI response/error bubble rendered |
| Browser: input cleared after send | Yes |
| Browser: error state | `AI Gateway · خطا` + error message (no fake success) |
| Browser: page-aware refresh | re-populates |
| Browser: console errors | **0** |

No paid model calls during these tests.

---

## 15. Explicit Confirmation: No Paid Calls

- `mock_mode=false` but **no real provider API keys configured** (all real providers `healthy=false`, "not configured").
- Mock provider is local, free, always healthy — no external inference.
- Automated pytest uses in-memory test DB + loopback-only socket guard — **0 outbound calls**.
- No `.env` credentials in logs/fixtures/browser automation.

---

## 16. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only readiness `GET /api/ai/status` (no writes).
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB needed (no backend change, no fixture writes).
- No test sessions/messages created in primary DB (no session domain exists).
- No secrets printed; dev API key read in-process from `.env` only.

---

## 17. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy |
| Temp container | `gi_backend_cand_6a30` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` preserved |
| Volumes | untouched |
| Working-tree `index.html` SHA-256 | `1af121b49f61f40672288bd542aa5a35099caab5b74d2d9ef7d38c533ee87a7c` |
| Container served hash | **identical** |

Change baked into image layer (not `docker cp`-only). Rollback images/container `e1cb5c747cee` (`rollback-step6a14`) preserved.

---

## 18. Source Hash Comparisons

- Candidate image SHA-256: `26313fdd65b99bade681eb5aa1cd3e3abe4c72225aa2940c383055ab92ed1369`
- `backend/static/index.html` working-tree hash: `1af121b49f61f40672288bd542aa5a35099caab5b74d2d9ef7d38c533ee87a7c`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 19. Exact Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | +`aiChatPage()`, +`aiChatSend()`, +`loadAiChat()`; `renderPage()` ai-chat routing; `pageRenderers` reference fix (`aiChat`→`aiChatPage`); loader wiring; page-aware refresh; dead legacy `sendChat()` commented out |

**Changed files: 1** (single-file frontend edit; no backend change). `+721 / −33` lines.

---

## 20. Carry-Forward Items

Unchanged from STEP 6A.29:
- **Providers:** browser execution of provider enable/disable still to be verified later using disposable test configuration; credentials remain write-only; provider test/model discovery remain disabled to prevent paid external calls.
- **Alerts:** `ackAlert`/`resolveAlert` browser execution still requires controlled verification on disposable alert records; never mutate primary alert records.
- **World Monitor:** third-party basemap dependency; no local/offline basemap fallback; mapping gap for excluded coordinate-bearing records without explicit location classification.

AI Chat adds:
- **No session/message persistence:** stateless `/api/ai/chat` only — UI does not claim session list/create/history/persistence. If persistence is required in a later stage, backend domain (`ChatSession`/`Message` models + routers) must be added first.

---

## 21. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | **API** | **Yes (NEW)** | AI Gateway conversation; `is_mock`/provider/model attribution; stateless (no session persistence domain) |
| 4 | `debate` | API | Yes | Debate |
| 5 | `evaluation` | Static | No | 0 human reviews |
| 6 | `evidence` | API | Yes | Claims & Evidence |
| 7 | `entity-graph` | API | Yes | Entity Graph + SVG visualization |
| 8 | `forecasts` | API | Yes | |
| 9 | `risk` | API | Yes | |
| 10 | `decisions` | API | Yes | |
| 11 | `inbox` | API | Yes | |
| 12 | `world` | API + 2D map | Yes | World Monitor (6A.25) |
| 13 | `geopolitics` | Static | No | 0 assessments |
| 14 | `iran` | API | Yes | Iran brief (6A.26) |
| 15 | `macro` | Static | No | 0 assessments, 239 observations |
| 16 | `markets` | API | Yes | Markets |
| 17 | `portfolio` | Static | No | 0 portfolios |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | API | Yes | Provider catalog/config (6A.27) |
| 21 | `operations` | API | Yes | Ops health/status monitoring (6A.28) |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | API | Yes | App configuration control plane (6A.29) |

**Total API-integrated: 19 of 25** (was 18 of 25).

---

## 22. Remaining Limitations

1. **No session/message persistence:** stateless `/api/ai/chat` only — no session list/create/open/history/delete. Honestly not claimed.
2. **No real provider configured:** mock provider is the only healthy one; live UI shows structured error when no provider key — not fake success.
3. **World Monitor basemap** still depends on `tiles.openfreemap.org` (external, unrelated).
4. **Alerts ack/resolve browser verification** remains **DEFERRED**.
5. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.

---

## 23. Next Recommended Stage

Per the stop condition, exactly one page (`ai-chat`) was implemented end-to-end. The next highest-value remaining page based on verified backend readiness is **`archive`** (registered catalog/storage endpoints) — chosen by verified backend readiness, not visual novelty. No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `ai-chat` backend `POST /api/ai/chat` already complete (`ai.py`); returns provider/model/is_mock/usage/latency; zero backend change needed | **VERIFIED** |
| F2 | Mock provider healthy, no real providers → no paid calls possible | **VERIFIED** |
| F3 | `aiChatPage()` + `aiChatSend()` + `loadAiChat()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F4 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `ai-chat` | **IMPLEMENTED_AND_TESTED** |
| F5 | Error handling honest (no fake success); attribution + execution-mode labeling | **VERIFIED** |
| F6 | No session persistence claimed (stateless domain absent) | **VERIFIED** |
| F7 | 141/141 backend tests pass (81 AI + 60 regression); 0 console errors browser | **VERIFIED** |
| F8 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F9 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F10 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`ai-chat`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 19 of 25 API-integrated.
