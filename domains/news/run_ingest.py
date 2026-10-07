"""Ingest news from all active sources (Phase 8 CLI).

اجرا:
    python -m domains.news.run_ingest            # همه‌ی منابع فعال
    python -m domains.news.run_ingest --limit 10
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from backend.database.models.source import Source
from backend.database.session import get_session_factory
from domains.news.ingestion import NewsIngestionPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest news for active sources")
    parser.add_argument("--limit", type=int, default=20, help="max items per source")
    parser.add_argument("--source", type=str, default=None, help="only this source name")
    args = parser.parse_args()

    session = get_session_factory()()
    total_stored = 0
    try:
        stmt = select(Source).where(Source.active.is_(True))
        if args.source:
            stmt = stmt.where(Source.name == args.source)
        sources = list(session.execute(stmt).scalars().all())

        pipeline = NewsIngestionPipeline(session)
        for source in sources:
            result = pipeline.ingest_source(source, limit=args.limit)
            total_stored += result.stored
            print(
                f"[{source.name}] fetched={result.fetched} stored={result.stored} "
                f"dup={result.duplicates} errors={len(result.errors)}"
            )
    finally:
        session.close()
    print(f"total stored: {total_stored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
