"""Run article classification (Phase 10 CLI).

اجرا:
    python -m domains.news.run_classify --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.news.classifier import ArticleClassifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify unclassified articles")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = asyncio.run(ArticleClassifier(session).classify_pending(limit=args.limit))
    finally:
        session.close()
    print(json.dumps(
        {"classified": outcome.classified, "failed": outcome.failed, "errors": outcome.errors},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
