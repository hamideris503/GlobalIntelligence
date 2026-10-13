"""CLI ربات: یک‌باره / مستمر / تک‌منبع.

    python -m source_bot.run_bot --once
    python -m source_bot.run_bot --source "BBC Business"
    python -m source_bot.run_bot --forever --poll 300
"""
from __future__ import annotations

import argparse
import asyncio
import json

from source_bot.runner import run_forever, run_once


def main() -> None:
    ap = argparse.ArgumentParser(description="Source bot runner")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--source", default=None)
    ap.add_argument("--poll", type=int, default=300)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    if args.forever:
        asyncio.run(run_forever(poll_seconds=args.poll))
        return
    metrics = asyncio.run(run_once(source_name=args.source, limit_sources=args.limit))
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
