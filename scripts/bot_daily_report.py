"""گزارش روزانهٔ Source Bot به تفکیک منبع — فقط خواندن؛ هیچ استخراج/شبکه‌ای ندارد.

    python -m scripts.bot_daily_report --day 2026-10-18
    python -m scripts.bot_daily_report --days 7 --out data/cache/bot_reports/week.json

پیش‌فرض: چاپ JSON روی stdout (قابل pipe). با `--out` در مسیر انتخابی نوشته
می‌شود؛ مسیر خروجی باید گیت‌ایگنور باشد (`data/cache/` یا `logs/`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from backend.database.session import get_session_factory
from source_bot.report import build_daily_report, job_records, range_bounds


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily Source Bot report (read-only)")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--day", help="یک روز UTC به شکل YYYY-MM-DD")
    group.add_argument("--days", type=int, help="N روز آخر UTC (۱ تا ۳۶۵)")
    ap.add_argument("--out", help="مسیر فایل خروجی (پیشنهاد: پوشهٔ گیت‌ایگنور)")
    args = ap.parse_args()
    if args.days is not None and not 1 <= args.days <= 365:
        ap.error("--days must be between 1 and 365")

    start, end, day = range_bounds(day=args.day, days=args.days)
    session = get_session_factory()()
    try:
        records = job_records(session, start=start, end=end)
    finally:
        session.close()
    report = build_daily_report(records, start=start, end=end, day=day)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"report written: {path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
