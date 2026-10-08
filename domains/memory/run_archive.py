"""Archive historical memory (Phase 19 CLI).

اجرا:
    python -m domains.memory.run_archive
    python -m domains.memory.run_archive --limit 200
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.memory.service import HistoricalMemoryService


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive historical memory")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = HistoricalMemoryService(session).archive_all(limit=args.limit)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
