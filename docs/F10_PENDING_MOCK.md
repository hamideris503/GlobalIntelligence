# F10 — رسیدگی کنترل‌شده به pending/Mock قدیمی

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

Pending/Mock history is handled by the screening orchestrator (`backend/ai/local_screening/`) and
recovery paths (`test_screening_recovery`): bounded retries, explicit pending status, and separation of
Mock from Real (mock results are never overwritten onto real results, and Mock is stripped from the
production chain). Tests: 71 passed. The re-enqueue loop noted in F01 (terminal rows re-entering the
cycle) remains a known follow-up and must be decided in F09/F10 (still open).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_screening_orchestrator.py` + `test_screening_recovery.py` + `test_screening_ops.py` + `test_mock_mode_unified.py` | 71 passed |
| Mock/Real separation | تأیید شد (کد/تست) |
| pending status صریح | تأیید شد |
| re-enqueue loop (F01) | هنوز تصمیم‌گیری نشده (باز) |

## ۲) محدودیت صریح

- رفتار re-enqueue ردیف‌های terminal پس از restart (F01) هنوز تصمیم‌گیری نشده.
- live screening روی دادهٔ واقعی اجرا نشد.
