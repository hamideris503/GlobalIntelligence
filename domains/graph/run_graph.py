"""Run knowledge-graph extraction over stored events (Phase 15 CLI).

اجرا:
    python -m domains.graph.run_graph --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.graph.engine import KnowledgeGraphEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Build knowledge graph from events")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = asyncio.run(KnowledgeGraphEngine(session).run(limit=args.limit))
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
