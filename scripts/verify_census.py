"""Live census verification (Step: census, background batches).

برای هر منبع PENDING: homepage را می‌گیرد، redirect نهایی را ثبت می‌کند و
وضعیت را فقط بر اساس مدرک تعیین می‌کند (VERIFIED فقط با 2xx واقعی).
هیچ‌چیز حدس زده نمی‌شود؛ رکوردهای ACTIVE قبلی دست نمی‌خورند.

اجرا:
    python -m scripts.verify_census --limit 60 --offset 0 --delay 1.5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, ".")

from sqlalchemy import select

from backend.database.models.source import Source
from backend.database.session import get_session_factory
from domains.news.source_verify import fetch_url

STATUS_MAP = {
    # error_kind -> validation_status
    "blocked": "NEEDS_REVIEW",
    "http_404": "NEEDS_REVIEW",  # ممکن است 404 ضدربات باشد، نه URL غلط
    "http_4xx": "NEEDS_REVIEW",
    "http_5xx": "TEMPORARILY_UNAVAILABLE",
    "timeout": "TEMPORARILY_UNAVAILABLE",
    "dns_or_connect": "NEEDS_REVIEW",
    "ssrf_blocked": "INVALID_URL",
    "invalid_url": "INVALID_URL",
    "too_big": "VERIFIED",  # 200 با بدنه‌ی بزرگ: URL معتبر است
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify pending census sources")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    session = get_session_factory()()
    stats = {"verified": 0, "needs_review": 0, "temp_unavail": 0,
             "invalid": 0, "errors": []}
    try:
        rows = list(session.execute(
            select(Source)
            .where(Source.validation_status == "PENDING_VALIDATION",
                   Source.homepage_url.is_not(None))
            .order_by(Source.priority.asc().nullslast(), Source.name)
            .limit(args.limit).offset(args.offset)
        ).scalars().all())
        print(f"batch: {len(rows)} sources", flush=True)
        for i, src in enumerate(rows):
            try:
                res = fetch_url(src.homepage_url or "", timeout=25.0)
                src.last_checked_at = datetime.now(UTC)
                if res.ok and res.final_url:
                    src.canonical_url = res.final_url
                    src.validation_status = "VERIFIED"
                    src.last_error = None
                    stats["verified"] += 1
                else:
                    mapped = STATUS_MAP.get(res.error_kind or "", "NEEDS_REVIEW")
                    if (res.error_kind or "").startswith("fetch_error"):
                        mapped = "NEEDS_REVIEW"
                    src.validation_status = mapped
                    src.last_error = f"{res.error_kind} @ {res.final_url or src.homepage_url}"[:500]
                    if mapped == "NEEDS_REVIEW":
                        stats["needs_review"] += 1
                    elif mapped == "TEMPORARILY_UNAVAILABLE":
                        stats["temp_unavail"] += 1
                    else:
                        stats["invalid"] += 1
                session.commit()
                print(f"[{i + 1}/{len(rows)}] {src.name}: "
                      f"{src.validation_status} ({res.error_kind or res.status_code})", flush=True)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                stats["errors"].append(f"{src.name}: {type(exc).__name__}")
            time.sleep(args.delay)
    finally:
        session.close()
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
