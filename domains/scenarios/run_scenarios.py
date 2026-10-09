"""Build scenarios for a target (Phase 30 CLI).

اجرا:
    python -m domains.scenarios.run_scenarios --target macro:inflation:USA
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.scenarios.engine import ScenarioEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scenarios for a target")
    parser.add_argument("--target", type=str, required=True)
    parser.add_argument("--method", type=str, default="naive")
    parser.add_argument("--horizon", type=str, default="short")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = ScenarioEngine(session).run(
            target=args.target, method=args.method, horizon=args.horizon
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
