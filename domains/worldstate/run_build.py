"""Build current world state snapshot (Phase 18 CLI).

اجرا:
    python -m domains.worldstate.run_build
    python -m domains.worldstate.run_build --granularity daily
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.worldstate.builder import WorldStateBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build world state snapshot")
    parser.add_argument("--granularity", type=str, default="daily")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = WorldStateBuilder(session).build(granularity=args.granularity)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
