"""Analyze social mood (Phase 23 CLI).

اجرا:
    python -m domains.society.run_analyze
    python -m domains.society.run_analyze --period 2026-10
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.society.analysis import SocialEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze social mood")
    parser.add_argument("--period", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = SocialEngine(session).analyze_all(period=args.period)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
