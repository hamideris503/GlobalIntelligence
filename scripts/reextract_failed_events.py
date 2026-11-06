"""Re-extract events whose AI extraction previously failed (stage 3.7).

Dry-run by default. When a real provider is configured, runs EventExtractor on
pending clusters with a bounded batch size, retry/backoff and an automatic
stop after too many consecutive failures. Never overwrites human-verified
values (extractor only fills empty fields via the deterministic fallback).
"""
from __future__ import annotations

import argparse
import asyncio

from backend.core.mock_mode import effective_mock_mode
from backend.database.session import get_db
from domains.events.extractor import EventExtractor


def dry_run(limit: int) -> None:
    from sqlalchemy import select

    from backend.database.models.event import Event

    db = next(get_db())
    try:
        total = db.execute(select(Event)).scalars().all()
        failed = [e for e in total if not (e.event_metadata or "").find('"used_ai": true') >= 0]
        print("total events:", len(total))
        print("events without successful AI extraction:", len(failed))
        print("limit:", limit)
    finally:
        db.close()


async def apply_run(limit: int, delay: float, max_failures: int) -> None:
    if effective_mock_mode():
        print("MOCK_MODE is active: AI extraction would return mock. Aborting apply.")
        return
    consecutive = 0
    processed = 0
    while processed < limit and consecutive < max_failures:
        db = next(get_db())
        try:
            extractor = EventExtractor(db)
            outcome = await extractor.run(limit=min(10, limit - processed))
            processed += outcome.events_created
            print(f"batch: created={outcome.events_created} linked={outcome.articles_linked} "
                  f"failed={outcome.failed} skipped={outcome.skipped}")
            if outcome.failed > 0:
                consecutive += outcome.failed
            else:
                consecutive = 0
            if outcome.events_created == 0 and outcome.failed == 0 and outcome.skipped == 0:
                print("no more pending clusters; stopping")
                break
        except Exception as exc:  # noqa: BLE001
            consecutive += 1
            print("batch exception:", type(exc).__name__, str(exc)[:200])
        finally:
            db.close()
        if consecutive < max_failures:
            await asyncio.sleep(delay)
    print(f"processed={processed} consecutive_failures={consecutive}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-failures", type=int, default=3)
    args = parser.parse_args()
    if not args.apply:
        dry_run(args.limit)
    else:
        asyncio.run(apply_run(args.limit, args.delay, args.max_failures))


if __name__ == "__main__":
    main()
