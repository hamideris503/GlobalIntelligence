"""GraphRAG-lite retrieval (Phase 52 CLI).

اجرا:
    python -m domains.research.run_graphrag --entities "Federal Reserve" "US Dollar"
    python -m domains.research.run_graphrag --entities X --synthesize
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.research.graphrag import GraphRAGService


def main() -> int:
    parser = argparse.ArgumentParser(description="GraphRAG-lite retrieval")
    parser.add_argument("--entities", nargs="+", required=True)
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--synthesize", action="store_true")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        service = GraphRAGService(session)
        ctx = service.retrieve(
            entity_names=args.entities, hops=args.hops, limit=args.limit
        )
        if args.synthesize:
            ctx.synthesis = asyncio.run(service.synthesize(ctx))
    finally:
        session.close()
    print(json.dumps(ctx.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
