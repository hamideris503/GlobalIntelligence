"""Build weekly intelligence briefing (Phase 42 CLI).

اجرا:
    python -m domains.briefings.run_weekly
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.briefings.weekly import WeeklyBriefingService


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weekly briefing")
    _ = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = WeeklyBriefingService(session).build()
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
