"""Run event extraction (Phase 11 CLI).

اجرا:
    python -m domains.events.run_extract --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.events.extractor import EventExtractor


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract events from article clusters")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = asyncio.run(EventExtractor(session).run(limit=args.limit))
    finally:
        session.close()
    print(json.dumps(
        {
            "events_created": outcome.events_created,
            "articles_linked": outcome.articles_linked,
            "failed": outcome.failed,
            "errors": outcome.errors,
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
