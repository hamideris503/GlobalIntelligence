# F08 — Priority و relevance

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

Priority (P0–P4) is computed deterministically in `source_bot/priority_engine.py` (`score_item`,
`priority_provenance`) with provenance (rules confidence, AI decision source, reason codes).
Relevance/screening (Kev/Laya/Rules/AI Gateway) is a separate concept from priority — Kev/Laya are
advisory and never replace deterministic rules or the cloud classifier (per AGENTS.md screening rule).
`ai_priority_fallback.py` only overrides priority when a real (non-mock) AI result is accepted; mock
results keep rules-based priority with `RULES_MOCK_AI`/`RULES_FALLBACK_AI_UNAVAILABLE` status. Tests:
`test_priority_provenance`, `test_priority_thresholds_levels`, `test_priority_keywords_config`,
`test_source_bot_priority_columns`, `test_source_bot_priority_dedup` pass.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_priority_provenance.py` + `test_priority_thresholds_levels.py` + `test_priority_keywords_config.py` + `test_source_bot_priority_columns.py` + `test_source_bot_priority_dedup.py` | پاس |
| priority provenance (rules_confidence, AI) | پوشش داده شده |
| mock → rules (نه AI) | پوشش داده شده (صداقت mock) |
| priority ≠ relevance (Kev/Laya advisory) | قرارداد کد |

## ۲) محدودیت صریح

- آستانه‌ها/confidence هنوز empirically calibrated نشده‌اند (F-24)؛ تا آن زمان version/limitation ثبت شده.
- Kev/Laya فقط prefilter/advisory می‌مانند (F04 held-out pending).
