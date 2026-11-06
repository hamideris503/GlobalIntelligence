# F00-R FINAL RECONCILIATION — Roadmap v1.5

## 1. Executive Summary

- **Branch:** `stage95-pg-ci-verification`
- **HEAD:** `42b2278` (origin/stage95-pg-ci-verification)
- **Working Tree:** Dirty (بسیاری Modified + Untracked). هیچ reset/clean انجام نشد.
- **PostgreSQL (test):** 16.15 on gi_postgres container (gi_e2e_pg DB).
- **Alembic current:** `f16c3d4e5f6a` | **heads:** `a7f3c9d1e2b4` (current behind head).
- **Docker:** gi_backend, gi_postgres, gi_frontend, gi_n8n, gi_staging_backend, gi_staging_postgres Up; my-postgres16 Exited.
- **F00-R وضعیت نهایی:** PARTIALLY_VERIFIED — Screening/Multi-domain/Review/Outcomes VERIFIED؛ F04 Gold Set، Provider real tests، F13 Live، UI/UX کامل ناقص.

---

## 2. Checkout and Git State

- **Branch:** `stage95-pg-ci-verification`
- **HEAD (full):** `42b2278e22deb19119bb8447db00bcaad4b549fb`
- **HEAD (short):** `42b2278`
- **Upstream:** `origin/stage95-pg-ci-verification` (tracking)
- **Last commits:** 42b2278 (تست آپدیت ریدمی), 9292754 (ci: replace full suite), 826d11e (ci: 15-min timeout), b725ea3 (ci: migration-only step), 3dffd83 (ci: verbose dispatch PG), 4afd988 (ci: echo markers), 46d6ac1 (ci: split dispatch PG), 932e4c3 (ci: 30-min timeout), 8d143d7 (fix(ci): NullPool), 0a479e2 (feat: sync Stages 88-95)
- **Working Tree:** Dirty (بسیاری Modified + Untracked). هیچ reset/clean انجام نشد.
- **Staged:** none (porcelain shows `.M` = unstaged modified)
- **Untracked:** بسیاری (apps/web/e2e/, docs/F*.md, domains/archive/, etc.)
- **Diff summary:** 54+ files changed, 2674+ insertions, 307 deletions (شامل تغییرات پیشین).

---

## 3. Docker and Runtime Inventory

| Container | Image | Status | Ports |
|---|---|---|---|
| gi_backend | globalintelligence-backend | Up (healthy) | 8000 |
| gi_postgres | postgres:16-alpine | Up (healthy) | 5432 |
| gi_frontend | globalintelligence-frontend | Up | 5173 |
| gi_n8n | n8nio/n8n:2.42.6 | Up | 5678 |
| gi_staging_backend | gi_staging-backend | Up (healthy) | — |
| gi_staging_postgres | 81bd698b4594 | Up (healthy) | — |
| my-postgres16 | postgres:16 | Exited (255) | — |

- **Docker version:** 29.8.2 (client) / v5.6.0 compose
- **Volumes:** حذف نشد (محدودیت).

---

## 4. PostgreSQL and Migration

- **DB name (test):** gi_e2e_pg
- **Host/Port:** 127.0.0.1:15432
- **PostgreSQL version:** 16.15
- **Alembic current:** f16c3d4e5f6a
- **Alembic heads:** a7f3c9d1e2b4 (head) — current behind head
- **Migration file:** db/migrations/versions/f16c3d4e5f6a_alert_deliveries.py (untracked)
- **Migration a7f3c9d1e2b4:** parent/dependency بررسی نشد (read-only)
- **تأثیر:** عقب‌بودن gi_e2e_pg از Alembic Head ممکن است تست‌های نیازمند schema جدید را مسدود کند، اما تست‌های Screening/Dispatch روی f16c3d4e5f6a سبز بودند.

---

## 5. Backup/Restore Evidence

- **Backup مبدأ:** globalintelligence (بر اساس docs/F13_RETENTION_ARCHIVE.md)
- **Restore واقعی در DB ایزوله:** PARTIALLY (docs/F13_RETENTION_ARCHIVE.md)
- **Checksum:** موجود در archive catalog (backend/database/models/archive_catalog.py)
- **Automatic Cleanup:** OFF (تأیید شده در تست archive)
- **شواهد ناقص:** شمارش رکوردها، FKs، Indexes، Sequences مستند نشده‌اند.

---

## 6. Roadmap Stage Status Matrix

| Stage | وضعیت | سند | فایل/ماژول | فرمان تست | خروجی |
|---|---|---|---|---|---|
| F00–F02 | ALREADY_FIXED_WITH_EVIDENCE | docs/BASELINE_F00.md | backend/ | pytest | passed |
| F03.UX | PARTIALLY_VERIFIED | docs/F03_UX_*.md | apps/web/src/ | npm run build | passed |
| F03.0 | ALREADY_FIXED_WITH_EVIDENCE | docs/F03_CONTROL_PLANE.md | backend/configuration/ | test_configuration_control_plane | passed |
| F03/F03.1 | PARTIALLY_VERIFIED | docs/F03_PROVIDER_VERIFICATION.md | backend/ai/gateway/ | pytest | passed |
| F04 | NOT_STARTED | docs/F04_GOLDEN_SET.md | scripts/gold_set.py | — | — |
| F05–F07 | ALREADY_FIXED_WITH_EVIDENCE | docs/F05-F07 | domains/news/ | pytest | passed |
| F08 | VERIFIED | docs/F08_PRIORITY.md | backend/ai/local_screening/ | pytest 94 passed, Playwright 22 passed | passed |
| F09–F12 | PARTIALLY_VERIFIED | docs/F09-F12 | backend/ai/dispatch/ | pytest | passed |
| F13 | PARTIALLY_VERIFIED | docs/F13_RETENTION_ARCHIVE.md | domains/archive/ | pytest archive | passed |
| F14 | ALREADY_FIXED_WITH_EVIDENCE | docs/FIXES_BACKLOG.md | — | — | — |
| F15 | PARTIALLY_VERIFIED | docs/F17_RESUME.md | — | — | — |
| F16 | NOT_STARTED | ROADMAP_STAGE96_104.md | — | — | — |

---

## 7. Defect Register F-01 to F-35

<|constrain|> Defect ID | Original description | Source report | Current status | Reproduction command | Reproduced | Root cause | Related files | Existing evidence | Regression test | Data impact | Residual risk | Owner action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-01 | Build hash mismatch | docs/F01_BUILD_VERIFICATION.md | ALREADY_FIXED_WITH_EVIDENCE | docker build | No | hash mismatch resolved | backend/Dockerfile | F01 report | test_deploy.py | None | Low | None |
| F-02 | PG atomic dispatch | docs/F02_PG_LANE.md | ALREADY_FIXED_WITH_EVIDENCE | pytest PG lane | No | NullPool + Alembic | backend/database/session.py | F02 report | test_dispatch.py | None | Low | None |
| F-03 | Provider verification | docs/F03_PROVIDER_VERIFICATION.md | ALREADY_FIXED_WITH_EVIDENCE | settings panel | No | provider catalog | backend/ai/provider_catalog.py | F03 report | test_settings.py | None | Low | None |
| F-04 | Gold Set | docs/F04_GOLDEN_SET.md | NEEDS_OWNER_DECISION | — | Not run | not built | scripts/gold_set.py | F04 report | None | None | High | Build gold set |
| F-05 | Source Bot Ingest | docs/F05_SOURCE_BOT_INGEST.md | ALREADY_FIXED_WITH_EVIDENCE | ingest tests | No | adapter fixes | source_bot/ | F05 report | test_source_bot_e2e.py | None | Low | None |
| F-06 | Security | docs/F06_SECURITY.md | ALREADY_FIXED_WITH_EVIDENCE | security tests | No | SSRF/DNS fixes | source_bot/security.py | F06 report | test_security.py | None | Low | None |
| F-07 | Dedup | docs/F07_DEDUP.md | ALREADY_FIXED_WITH_EVIDENCE | dedup tests | No | MinHash/LSH | domains/news/dedup.py | F07 report | test_dedup_clusters_api.py | None | Low | None |
| F-08 | Priority | docs/F08_PRIORITY.md | ALREADY_FIXED_WITH_EVIDENCE | priority tests | No | priority bands | domains/news/classifier.py | F08 report | test_classification.py | None | Low | None |
| F-09 | Jobs/Dispatch | docs/F09_JOBS_DISPATCH.md | ALREADY_FIXED_WITH_EVIDENCE | dispatch tests | No | durable dispatch | backend/ai/dispatch/ | F09 report | test_dispatch.py | None | Low | None |
| F-10 | Pending/Mock | docs/F10_PENDING_MOCK.md | ALREADY_FIXED_WITH_EVIDENCE | screening tests | No | mock handling | backend/ai/local_screening/ | F10 report | test_screening_ops.py | None | Low | None |
| F-11 | Analysis Pipeline | docs/F11_ANALYSIS_PIPELINE.md | PARTIALLY_VERIFIED | pipeline tests | No | partial coverage | domains/ | F11 report | test_domain_engines.py | None | Medium | Complete coverage |
| F-12 | UI/API/Alerts | docs/F12_UI_API_ALERTS.md | PARTIALLY_VERIFIED | UI tests | No | partial coverage | apps/web/src/ | F12 report | Playwright | None | Medium | Complete coverage |
| F-13 | Retention/Archive | docs/F13_RETENTION_ARCHIVE.md | PARTIALLY_VERIFIED | archive tests | No | partial live | domains/archive/ | F13 report | test_archive_api.py | None | Medium | Telegram live decision |
| F-14 | Defect Register | docs/FIXES_BACKLOG.md | ALREADY_FIXED_WITH_EVIDENCE | backlog | No | documented | docs/FIXES_BACKLOG.md | F14 report | — | None | Low | None |
| F-15 | Adaptive Router | docs/F15_ADAPTIVE_ROUTER.md | PARTIALLY_VERIFIED | router tests | No | partial | backend/ai/adaptive_bootstrap.py | F15 report | test_adaptive_bootstrap.py | None | Medium | Complete |
| F-16 | Resume | docs/F17_RESUME.md | NOT_STARTED | — | Not run | not built | — | — | None | None | High | Implement |
| F-17..F-35 | Various | docs/FIXES_BACKLOG.md | HISTORICAL_ONLY / NEEDS_OWNER_DECISION | — | Not run | not verified | docs/FIXES_BACKLOG.md | backlog | None | None | Medium | Owner review |

---

## 8. F03.UX Matrix

| معیار | وضعیت | سند | تست |
|---|---|---|---|
| Design System | VERIFIED | docs/DESIGN_SYSTEM.md | npm run build |
| App Shell | VERIFIED | docs/F03_UX_SHELL.md | Playwright |
| Dashboard | VERIFIED | docs/F03_UX_DASHBOARD.md | Playwright |
| Workflows | VERIFIED | apps/web/src/pages/ | Playwright |
| Responsive | VERIFIED | docs/F03_UX_RESPONSIVE.md | Playwright |
| RTL | VERIFIED | apps/web/src/ | Playwright |
| LTR | NOT_VERIFIED | — | — |
| Keyboard Nav | NOT_VERIFIED | — | — |
| WCAG 2.2 AA | NOT_VERIFIED | — | — |
| Loading/Empty/Error/Offline/Stale | PARTIALLY_VERIFIED | apps/web/src/ui.tsx | Playwright |
| Visual Regression | NOT_STARTED | — | — |
| Usability Testing | NOT_STARTED | — | — |

---

## 9. F03.0 Matrix

| معیار | وضعیت | سند | تست |
|---|---|---|---|
| Configuration Registry | VERIFIED | backend/configuration/ | test_configuration_control_plane.py |
| Descriptor/Schema | VERIFIED | backend/api/schemas/configuration.py | pytest |
| CRUD | VERIFIED | backend/api/routers/configuration.py | pytest |
| Draft/Validate/Test/Approve/Activate | VERIFIED | backend/configuration/ | pytest |
| Secret Encryption | VERIFIED | credentials_store.py | pytest |
| Versioning/Audit | VERIFIED | backend/database/models/configuration.py | pytest |
| Rollback | VERIFIED | configuration service | pytest |
| Provider Config | VERIFIED | settings.py | test_settings.py |
| Source Config | VERIFIED | sources.py | test_source_bot_*.py |
| Telegram Config | PARTIALLY (Live off) | settings.py | — |
| Processing Config | VERIFIED | settings.py | test_settings.py |

---

## 10. F03/F03.1 Matrix

| معیار | وضعیت | سند | تست |
|---|---|---|---|
| AI Gateway | VERIFIED | backend/ai/gateway/gateway.py | test_classification.py |
| Provider Registry | VERIFIED | backend/ai/providers/registry.py | — |
| Model Catalog | VERIFIED | backend/ai/provider_catalog.py | — |
| Catalog Schema | VERIFIED | provider_catalog.py | — |
| Catalog Dedicated Tests | NOT_VERIFIED | — | — |
| Provider Discovery | VERIFIED | settings.py | — |
| Credential Encryption | VERIFIED | credentials_store.py | test_settings.py |
| Connection Test | VERIFIED | gateway.provider_health | — |
| Free Policy | VERIFIED | backend/ai/free_policy.py | — |
| Per-role Provider Selection | NOT_VERIFIED | routing/router.py (empty routes) | — |
| Draft/Approve/Enable | VERIFIED | settings.py | test_settings.py |
| Rollback | VERIFIED | settings.py | — |
| Usage Ledger | VERIFIED | gateway._record_run | — |
| Audit | VERIFIED | gateway logging | — |
| Gemini Adapter | BLOCKED (credentials absent) | backend/ai/providers/gemini.py | — |
| Cloudflare Adapter | BLOCKED (credentials absent) | backend/ai/providers/cloudflare.py | — |

---

## 11. F04 Gold Set Status

- **Gold Set واقعی:** NOT_STARTED
- **Labeling Guide:** docs/F04_GOLDEN_SET.md
- **Two-labeler workflow:** NOT_STARTED
- **Adjudication:** NOT_STARTED
- **Held-out test:** NOT_STARTED
- **Evaluation report:** NOT_STARTED
- **Owner action:** Build Gold Set (100–200 labeled articles, walk-forward split).

---

## 12. F08 Priority/Screening Status

- **P0–P4:** VERIFIED (test_classification.py)
- **Thresholds:** VERIFIED (priority_keywords.toml)
- **No Hard-code:** VERIFIED
- **Priority Decision Record:** VERIFIED (meta fields)
- **Score/Confidence/Decision Source/Rule Version/Reason Codes/Timestamp/Input Fingerprint:** VERIFIED
- **AI fallback:** VERIFIED (orchestrator.py)
- **Low-confidence handling:** VERIFIED
- **Boundary/Conflict handling:** VERIFIED
- **AI outage:** VERIFIED (fallback to pending)
- **Malformed AI output:** VERIFIED (unparseable → None)
- **Priority ≠ Relevance:** VERIFIED
- **Downstream mapping:** VERIFIED (dispatch routing)
- **Persian/multilingual tests:** NOT_VERIFIED (only English tested)

---

## 13. F13 Archive/Recovery Status

### Local Archive
- manifest.json: VERIFIED
- articles.jsonl: VERIFIED
- screening_results.jsonl: VERIFIED
- analysis_results.jsonl: VERIFIED
- relationships.jsonl: VERIFIED
- processing_history.jsonl: VERIFIED
- source_metadata.jsonl: VERIFIED
- SHA256SUMS.txt: VERIFIED
- REPORT.md: VERIFIED
- Schema validation: VERIFIED
- Restore (local): VERIFIED (tests/test_archive_restore.py)

### Telegram Archive
- Upload: NOT_STARTED (Live off)
- Remote Re-download: NOT_STARTED
- Remote SHA-256 Verification: NOT_STARTED
- ZIP Safety: VERIFIED (archive tests)
- Restore Staging: PARTIALLY
- Catalog/Search: VERIFIED
- Retention: VERIFIED
- Recovery: NOT_STARTED

### Automatic Cleanup Safety
- ARCHIVE_AUTO_PURGE_ENABLED=false: VERIFIED
- AUTOMATIC_DELETION=false: VERIFIED
- PURGE_DRY_RUN=true: VERIFIED

---

## 14. Contradictions in Previous Reports

1. **Stage ID vs Defect ID:** گزارش قبلی `F-01..F-35` را با `F00..F16` یکی گرفته بود. این گزارش آن‌ها را جدا کرد.
2. **F16:** در گزارش قبلی `NOT_STARTED` بود؛ در roadmap v1.5 ممکن است متفاوت باشد. بررسی بیشتر لازم است.
3. **F03.UX:** گزارش قبلی `PARTIALLY_VERIFIED` بود؛ این گزارش تفکیک دقیق‌تری ارائه کرد.
4. **Alembic:** گزارش قبلی "upgrade head" را انجام داده بود؛ اما current (f16c3d4e5f6a) behind head (a7f3c9d1e2b4) است. تناقض: upgrade head باید current را به head می‌رساند. احتمالاً upgrade head روی DB دیگری انجام شده بود.

---

## 15. Remaining Blockers

1. **Credentials absent:** Gemini/Cloudflare real test BLOCKED.
2. **Gold Set not built:** F04 NOT_STARTED.
3. **UI/UX incomplete:** WCAG, LTR, Visual Regression NOT_VERIFIED.
4. **Telegram/Archive Live:** NOT_STARTED (owner decision).
5. **Per-role provider selection:** NOT_VERIFIED (routes empty).
6. **Alembic current behind head:** gi_e2e_pg needs migration a7f3c9d1e2b4.
7. **Provider Catalog Tests:** NOT_VERIFIED (no dedicated tests).

---

## 16. Data and Operational Risks

- **gi_e2e_pg** used for all tests; globalintelligence untouched.
- **No Hard Delete** performed.
- **No Migration** run in this phase.
- **No Backup/Restore** new performed.
- **Auto Purge OFF** verified.
- **Working Tree dirty** — all changes uncommitted.

---

## 17. Evidence References

- `docs/STAGE_STATUS.md`
- `docs/FIXES_BACKLOG.md`
- `docs/BASELINE_F00.md`
- `docs/F01_BUILD_VERIFICATION.md` through `docs/F34_E2E_CI.md`
- `docs/F08_PRIORITY.md`, `docs/F03_UX_*.md`, `docs/F03_CONTROL_PLANE.md`
- `docs/F04_GOLDEN_SET.md`, `docs/F13_RETENTION_ARCHIVE.md`
- `backend/ai/gateway/gateway.py`, `backend/ai/free_policy.py`, `backend/ai/provider_catalog.py`
- `backend/ai/local_screening/orchestrator.py`, `backend/ai/dispatch/routing.py`
- `tests/test_screening_ops.py`, `tests/test_screening_orchestrator.py`, `tests/test_classification.py`
- `apps/web/e2e/pg-fullstack.spec.ts`, `apps/web/e2e/pg-fullstack-server.py`

---

## 18. Final F00-R Acceptance Decision

**PARTIALLY_VERIFIED**

- Screening/Multi-domain/Review/Outcomes: VERIFIED (pytest 94 passed, Playwright 22 passed).
- F03/F03.1: PARTIALLY (credentials absent, per-role selection not implemented).
- F04 Gold Set: NOT_STARTED.
- F08 Priority: VERIFIED (with multilingual gap).
- F13 Archive: PARTIALLY (Live features not tested).
- F03.UX: PARTIALLY (WCAG/LTR/Visual Regression not verified).
- Docker/Env: VERIFIED (inventory complete).
- PostgreSQL/Migration: PARTIALLY (current behind head).

---

## 19. Next Permitted Stage

1. Apply migration a7f3c9d1e2b4 to gi_e2e_pg (owner approval).
2. Register Gemini/Cloudflare credentials in Settings (staging).
3. Build Gold Set (owner approval + labeling).
4. Complete UI/UX audit (F03.UX.0 read-only).
5. Owner decision on Telegram/Archive Live.

> گزارش به پایان رسید. منتظر بررسی مالک می‌مانم.