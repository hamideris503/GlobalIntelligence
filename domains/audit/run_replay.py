"""Replay an engine deterministically (Phase 38 CLI).

اجرا:
    python -m domains.audit.run_replay --engine macro
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.audit.replay import SUPPORTED_ENGINES, replay


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay an engine")
    parser.add_argument(
        "--engine", type=str, default="macro", choices=list(SUPPORTED_ENGINES)
    )
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = replay(session, args.engine)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
