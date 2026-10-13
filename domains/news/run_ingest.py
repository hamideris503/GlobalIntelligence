"""Ingest news from all active sources (Phase 8 CLI).

اجرا:
    python -m domains.news.run_ingest            # همه‌ی منابع فعال
    python -m domains.news.run_ingest --limit 10
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from backend.core.config import get_settings
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
        # AUDIT-REPAIR: همان فیلتر API (قبلاً همه‌ی منابع فعال بدون فیلتر بودند
        # و در production بی‌صدا ۰ ذخیره با موفقیت ثبت می‌شد)
        stmt = select(Source).where(Source.active.is_(True))
        if not get_settings().mock_mode:
            stmt = stmt.where(
                Source.collection_method == "rss", Source.feed_url.is_not(None)
            )
        if args.source:
            stmt = stmt.where(Source.name == args.source)
        sources = list(session.execute(stmt).scalars().all())

        # RELIABILITY: منابع ردشده دیگر بی‌صدا نیستند (E2E FIND)
        if not get_settings().mock_mode and not args.source:
            skipped = list(session.execute(
                select(Source).where(
                    Source.active.is_(True),
                    ((Source.collection_method != "rss")
                     | (Source.collection_method.is_(None))
                     | (Source.feed_url.is_(None))),
                )
            ).scalars().all())
            for s in skipped:
                reason = ("no feed_url" if not s.feed_url
                          else f"method={s.collection_method} not implemented in news pipeline")
                print(f"[{s.name}] SKIPPED: {reason}")

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
