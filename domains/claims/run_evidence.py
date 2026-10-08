"""Run evidence engine (Phase 13 CLI).

اجرا:
    python -m domains.claims.run_evidence --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.claims.evidence import EvidenceEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect evidence for claims")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = asyncio.run(EvidenceEngine(session).run(limit=args.limit))
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
