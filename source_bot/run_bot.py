"""CLI ربات: یک‌باره / مستمر / تک‌منبع.

    python -m source_bot.run_bot --once
    python -m source_bot.run_bot --source "BBC Business"
    python -m source_bot.run_bot --forever --poll 300
"""
from __future__ import annotations

import argparse
import asyncio
import json

from source_bot.runner import MAX_ITEMS_PER_SOURCE, run_forever, run_once


def _items_cap(value: str) -> int:
    """سقف پردازش هر منبع: عدد صحیح در [1, MAX_ITEMS_PER_SOURCE]؛ پیش از هر fetch."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--items must be an integer within [1, {MAX_ITEMS_PER_SOURCE}]") from exc
    if not 1 <= number <= MAX_ITEMS_PER_SOURCE:
        raise argparse.ArgumentTypeError(
            f"--items must be within [1, {MAX_ITEMS_PER_SOURCE}], got {number}")
    return number


def main() -> None:
    ap = argparse.ArgumentParser(description="Source bot runner")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--source", default=None)
    ap.add_argument("--poll", type=int, default=300)
    ap.add_argument("--limit", type=int, default=50,
                    help="حداکثر تعداد منابع در اجرای خودکار (نه تعداد خبر)")
    ap.add_argument("--items", type=_items_cap, default=None,
                    help=f"حداکثر آیتم پردازش‌شده از هر منبع در این اجرا (1..{MAX_ITEMS_PER_SOURCE})")
    args = ap.parse_args()
    if args.forever:
        asyncio.run(run_forever(poll_seconds=args.poll))
        return
    metrics = asyncio.run(run_once(source_name=args.source, limit_sources=args.limit,
                                  max_items_per_source=args.items))
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
