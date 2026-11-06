# F15 — AdaptiveRouter wired to runtime (F-15)

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

`AdaptiveRouter` was previously only reachable via the manual `/api/ai-routing/record` endpoint. It is now
wired into `AIGateway.generate`: after a successful call, one best-effort record is written (success=True);
on total failure, one record is written (success=False) for the last attempted provider. Preconditions met:
- Exactly one record per generate (success or total failure), not per retry/fallback.
- Zero records in `MOCK_MODE` (`effective_mock_mode()` guard).
- DB errors never break the AI response (wrapped in try/except, logged as warning).
- Separate short-lived session from `get_session_factory()` — no commit on the request session.
- Concurrency race on `uq_provider_run` handled (rollback + one retry; otherwise swallowed).
- `structured_ok` reflects `request.json_schema`.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_ai_gateway.py` + `test_classification.py` + `test_ai_chat.py` + `test_debate.py` + `test_settings.py` | 151 passed |
| `test_ai_routing.py` | پاس (در suite قبلی) |
| رکورد در Mock mode | صفر (guard) |
| خطای DB نشکند پاسخ AI را | try/except |
| یک رکورد per generate | یک فراخوانی |

## ۲) محدودیت صریح

- `AdaptiveRouter` هنوز به‌صورت خودکار `apply_routes` را صدا نمی‌زند؛ اعمال زنجیره همچنان دستی/endpoint است.
- رکورد فقط در صورت factory ثبت‌شده (production lifespan یا تست) انجام می‌شود.
- F-15 در نقشهٔ راه «اتصال خودکار» می‌خواهد؛ اعمال خودکار زنجیره (apply) هنوز باز است.
