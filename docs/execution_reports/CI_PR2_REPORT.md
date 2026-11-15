# CI — Pull Request #2 (step6a-analysis-dashboard → main)

- **تاریخ:** ۱۶ نوامبر ۲۰۲۶
- **HEAD:** `c8bfdff` · **PR:** #2 · **Run:** 43761925301
- **trigger:** `pull_request` (چون workflow فقط `push` روی `main` و `pull_request` را اجرا می‌کند)

## 1. نتیجهٔ اجرای اول

| Job | نتیجه | زمان |
|---|---|---|
| `backend` (PostgreSQL 16 + کل سوئیت) | **succeeded** | — |
| `docker` (build هر دو image) | **succeeded** | 39s |
| `backend-sqlite` (`pytest -m "not pg"`) | **failed** | 2m 15s |

Annotation موجود برای `backend-sqlite`: `Run SQLite-compatible tests — Process completed with exit code 1`.
نام تست شکست‌خورده در UI بدون ورود به GitHub قابل مشاهده نیست.

## 2. بازتولید محلی

| محیط | دستور | نتیجه |
|---|---|---|
| Windows، Python 3.14، همان envهای CI | `pytest ../tests -q -m "not pg" --basetemp=.pytest-sqlite` | **1928 passed / 2 skipped / EXIT=0** (609.83s) |
| Linux (`python:3.12-slim` container)، همان envها + `requirements*.txt` | همان دستور | **1926 passed / 4 skipped / EXIT=0** (245.33s) |

تفاوت ۱۹۲۶ و ۱۹۲۸ مربوط به skipهای وابسته به پلتفرم است (Unix-only tests روی Windows skip می‌شوند).

## 3. تفسیر

- هر سه job به‌جز یکی سبز است؛ job شکست‌خورده در **دو محیط مستقل** (از جمله exact image و Python 3.12 همانند CI) صفر failure داده است.
- بنابراین شکست فعلی **قابل بازتولید نیست** و به‌احتمال زیاد flaky/محیطی است (نه نقص کد).
- برای قطعیت، یک اجرای دوم CI لازم است؛ commit مستندات این گزارش، خودش CI را دوباره trigger می‌کند.

## 4. اقدام بعدی

1. نتیجهٔ اجرای دوم را در PR #2 ببینید.
2. اگر سبز شد → flake تأیید می‌شود (تست مشکوک شناسایی و مقاوم‌سازی می‌شود).
3. اگر همان job باز هم قرمز شد → با ورود به GitHub، نام تست از log خوانده و همان تست هدف اصلاح قرار می‌گیرد.
