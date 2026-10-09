"""Snapshot a portfolio (Phase 35 CLI).

اجرا:
    python -m domains.portfolio.run_snapshot --portfolio-id <uuid>
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.portfolio.engine import PortfolioEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot a portfolio")
    parser.add_argument("--portfolio-id", type=str, required=True, dest="portfolio_id")
    parser.add_argument("--period", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = PortfolioEngine(session).snapshot(
            portfolio_id=args.portfolio_id, period=args.period
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
