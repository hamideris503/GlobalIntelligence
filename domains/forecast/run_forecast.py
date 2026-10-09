"""Run baseline forecasts (Phase 25 CLI).

اجرا:
    python -m domains.forecast.run_forecast --target macro:inflation:USA
    python -m domains.forecast.run_forecast --target market:WTI --method naive --horizon medium
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.forecast.engine import ForecastEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Run baseline forecasts")
    parser.add_argument("--target", type=str, required=True)
    parser.add_argument("--method", type=str, default="all")
    parser.add_argument("--horizon", type=str, default="short")
    parser.add_argument("--scenario", type=str, default="base")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = ForecastEngine(session).run(
            target=args.target,
            method=args.method,
            horizon=args.horizon,
            scenario=args.scenario,
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
