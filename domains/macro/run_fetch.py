"""Fetch economic data from World Bank (Phase 16 CLI).

اجرا:
    python -m domains.macro.run_fetch --indicator inflation --country USA
    python -m domains.macro.run_fetch --all
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.macro.engine import EconomicDataService


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch economic data")
    parser.add_argument("--indicator", type=str, default=None)
    parser.add_argument("--country", type=str, default="USA")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--all", action="store_true", help="fetch all indicators/countries")
    parser.add_argument("--fetcher", type=str, default="world_bank")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        service = EconomicDataService(session, fetcher_name=args.fetcher)
        if args.all:
            outcome = asyncio.run(service.run(limit=args.limit))
        else:
            if not args.indicator:
                parser.error("--indicator is required (or use --all)")
            outcome = asyncio.run(
                service.fetch_indicator(
                    indicator=args.indicator, country=args.country, limit=args.limit
                )
            )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
