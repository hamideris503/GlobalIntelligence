# Remediation Backlog — GlobalIntelligence v1.5

## P0 (blocking merge/trust)
- F-02 deadlock `test_claim_is_atomic` — verify on PG lane (F02). Local: not reproduced in current run? Need PG run. (tracked)
- F-03 CI only subset — CI still runs focused subset; full suite not in CI. Action: update .github/workflows/ci.yml to run full pytest on PG. (not changed this run)

## P1 (correctness/reliability)
- F-14 JobRun race (check-then-insert) — needs unique partial index or atomic upsert. Not yet implemented.
- F-15 AdaptiveRouter not invoked at runtime — wire into gateway record path if needed.
- F-16 ETag state lost on adapter rebuild — persist in source config/DB.
- F-18 N+1 in graph/replay/macro context — profile first.
- F-19 heavy endpoints in request thread — move proven slow ones to durable jobs.
- F-23 rate limit in-process only — document limit; shared backend only if multi-process needed.
- F-24 thresholds not empirically calibrated — needs gold set (F04).

## P2 (debt)
- F-20 topics/entities Text vs JSON — only if schema contract requires.
- F-22 frontend lint/typecheck — lint passes (warnings only); typecheck passes.
- F-27 IPv6 policy — verify explicit support/limitation.
- F-28 ROADMAP.md stale — update reference.
- F-32 .gitignore patterns — review.
- F-33 untracked temp files — review contents for secrets.

## External blockers (cannot complete locally without input)
- F03 groq 403 (network/region/key).
- F04 human-labeled gold set.
- F12 live Telegram/Email send (needs TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SMTP_*).
- F13 live Telegram archive restore verification (needs bot token + chat id).
- CI remote verification (Python 3.12 / pytest<9).

## Completed this run
- Alert delivery real implementation (Telegram + SMTP) with retry/backoff, idempotency, secret-safe.
- Tests: tests/test_alert_delivery_live.py (7 passed).
- Ruff fix imports.
