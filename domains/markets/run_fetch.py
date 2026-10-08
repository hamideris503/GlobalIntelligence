"""Fetch market data (Phase 17 CLI).

اجرا:
    python -m domains.markets.run_fetch --symbol XAUUSD
    python -m domains.markets.run_fetch --all
    python -m domains.markets.run_fetch --asset-class energy
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.markets.engine import MarketDataService


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch market data")
    parser.add_argument("--symbol", type=str, default=None)
    parser.add_argument("--asset-class", type=str, default=None, dest="asset_class")
    parser.add_argument("--all", action="store_true", help="fetch all symbols")
    parser.add_argument("--fetcher", type=str, default="auto")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        service = MarketDataService(session, fetcher_name=args.fetcher)
        if args.symbol:
            outcome = asyncio.run(service.fetch_symbol(symbol=args.symbol))
        else:
            if not args.all and not args.asset_class:
                parser.error("one of --symbol, --asset-class or --all is required")
            outcome = asyncio.run(service.run(asset_class=args.asset_class))
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
