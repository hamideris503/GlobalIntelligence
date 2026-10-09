"""Learn from history (Phase 51 CLI).

اجرا:
    python -m domains.learning.run_learn
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.learning.engine import LearningEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn from history")
    parser.add_argument("--period", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = LearningEngine(session).run(period=args.period)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
