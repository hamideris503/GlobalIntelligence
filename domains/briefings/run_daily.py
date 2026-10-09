"""Build daily intelligence briefing (Phase 41 CLI).

اجرا:
    python -m domains.briefings.run_daily
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.briefings.daily import DailyBriefingService


def main() -> int:
    parser = argparse.ArgumentParser(description="Build daily briefing")
    parser.add_argument("--day", type=str, default=None)
    parser.add_argument("--window-hours", type=int, default=24, dest="window_hours")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = DailyBriefingService(session).build(
            day=args.day, window_hours=args.window_hours
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
