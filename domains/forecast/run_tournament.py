"""Run a forecast tournament (Phase 29 CLI).

اجرا:
    python -m domains.forecast.run_tournament --targets macro:inflation:USA market:WTI
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.forecast.tournament import TournamentEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Run forecast tournament")
    parser.add_argument("--targets", nargs="+", required=True)
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--horizon", type=str, default="short")
    parser.add_argument("--scenario", type=str, default="base")
    parser.add_argument("--name", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = TournamentEngine(session).run(
            targets=args.targets,
            methods=args.methods,
            horizon=args.horizon,
            scenario=args.scenario,
            name=args.name,
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
