"""Build narratives from events (Phase 24 CLI).

اجرا:
    python -m domains.narratives.run_build
    python -m domains.narratives.run_build --period 2026-10
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.narratives.engine import NarrativeEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Build narratives from events")
    parser.add_argument("--period", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = NarrativeEngine(session).build_all(period=args.period)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
