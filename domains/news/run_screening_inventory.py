"""Historical screening inventory planner (Stage100).

Read-only by default. Audits existing articles to determine which need
initial screening, which are eligible, and which require review.

Usage:
    python -m domains.news.run_screening_inventory
    python -m domains.news.run_screening_inventory --limit 500
    python -m domains.news.run_screening_inventory --manifest /path/to/manifest.json
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import select

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.session import get_session_factory


def _screening_meta(meta: dict) -> dict | None:
    v = meta.get("local_screening")
    return v if isinstance(v, dict) else None


def _classify_article(article: Article, doc: Document | None) -> dict:
    """Classify an article into a screening inventory category (read-only)."""
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}

    sm = _screening_meta(meta)
    dr = meta.get("domain_routing")
    dr = dr if isinstance(dr, dict) else None

    # Determine text availability
    has_text = bool(doc and doc.raw_text and doc.raw_text.strip())
    has_title = bool(doc and doc.title and doc.title.strip())
    priority = doc.ingestion_priority if doc else None

    # Determine screening status
    if sm is not None:
        decision = sm.get("decision")
        if decision is True:
            screening_status = "screened_relevant"
        elif decision is False:
            screening_status = "screened_not_relevant"
        else:
            screening_status = "screened_pending"
    else:
        screening_status = "not_screened"

    # Determine category
    if article.classification_status == "pending":
        category = "pending_classification"
    elif article.classification_status == "failed":
        category = "failed_classification"
    elif screening_status == "not_screened":
        if not has_text:
            category = "ineligible_no_text"
        else:
            category = "eligible_initial_screening"
    elif screening_status == "screened_pending":
        category = "screening_pending_retryable"
    else:
        category = "already_screened"

    # Determine routing status
    if dr is not None:
        routing_status = dr.get("state", "unknown")
    else:
        routing_status = "no_routing"

    return {
        "article_id": str(article.id),
        "classification_status": article.classification_status,
        "screening_status": screening_status,
        "category": category,
        "has_text": has_text,
        "has_title": has_title,
        "priority": priority,
        "routing_status": routing_status,
        "topics": json.loads(article.topics) if article.topics else [],
        "country": article.country,
        "event_type": None,  # filled later if event linked
    }


def _scan(session, limit: int) -> dict:
    """Scan articles and produce screening inventory (read-only)."""
    articles = list(session.execute(
        select(Article)
        .order_by(Article.retrieved_at.desc().nullslast())
        .limit(limit)
    ).scalars().all())

    # Load documents
    doc_ids = [a.document_id for a in articles if a.document_id]
    docs = {}
    if doc_ids:
        for d in session.execute(
            select(Document).where(Document.id.in_(doc_ids))
        ).scalars().all():
            docs[d.id] = d

    # Load events for event_type
    event_ids = [a.event_id for a in articles if a.event_id]
    events = {}
    if event_ids:
        from backend.database.models.event import Event
        for e in session.execute(
            select(Event).where(Event.id.in_(event_ids))
        ).scalars().all():
            events[e.id] = e

    categories = {
        "already_screened": 0,
        "eligible_initial_screening": 0,
        "screening_pending_retryable": 0,
        "failed_classification": 0,
        "pending_classification": 0,
        "ineligible_no_text": 0,
    }
    routing_statuses = {}
    priority_counts = {}
    event_type_counts = {}
    sample_eligible = []
    sample_review = []

    for art in articles:
        doc = docs.get(art.document_id)
        info = _classify_article(art, doc)
        if art.event_id and art.event_id in events:
            info["event_type"] = events[art.event_id].event_type

        cat = info["category"]
        categories[cat] = categories.get(cat, 0) + 1

        rs = info["routing_status"]
        routing_statuses[rs] = routing_statuses.get(rs, 0) + 1

        p = info["priority"] or "None"
        priority_counts[p] = priority_counts.get(p, 0) + 1

        et = info["event_type"] or "None"
        event_type_counts[et] = event_type_counts.get(et, 0) + 1

        if cat == "eligible_initial_screening" and len(sample_eligible) < 10:
            sample_eligible.append(info["article_id"])
        if cat in ("failed_classification", "ineligible_no_text") and len(sample_review) < 10:
            sample_review.append(info["article_id"])

    return {
        "total_scanned": len(articles),
        "categories": categories,
        "routing_statuses": routing_statuses,
        "priority_counts": priority_counts,
        "event_type_counts": event_type_counts,
        "sample_eligible": sample_eligible,
        "sample_review": sample_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Historical screening inventory (read-only)"
    )
    parser.add_argument("--limit", type=int, default=10000,
                        help="Max articles to scan")
    parser.add_argument("--manifest", type=str, default=None,
                        help="Path to write inventory manifest JSON")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        inventory = _scan(session, args.limit)

        # Build report
        report = {
            "mode": "read-only",
            "timestamp": datetime.now(UTC).isoformat(),
            "database_dialect": session.bind.dialect.name,
            "total_scanned": inventory["total_scanned"],
            "categories": inventory["categories"],
            "routing_statuses": inventory["routing_statuses"],
            "priority_counts": inventory["priority_counts"],
            "event_type_counts": inventory["event_type_counts"],
            "sample_eligible": inventory["sample_eligible"],
            "sample_review": inventory["sample_review"],
            "screening_entry_point": "backend.ai.local_screening.orchestrator.screen_with_db(db, text, level)",
            "screening_prerequisites": [
                "Article must have classification_status='done' (topics, country, sentiment set)",
                "Article must have non-empty text (document.raw_text)",
                "Kev/Laya enablement settings read from AppSetting table",
                "LocalRuntimeSupervisor must be available (not bypassed)",
            ],
            "eligible_for_future_screening": inventory["categories"].get("eligible_initial_screening", 0),
            "requires_review": inventory["categories"].get("failed_classification", 0) + inventory["categories"].get("ineligible_no_text", 0),
            "already_screened": inventory["categories"].get("already_screened", 0),
            "pending_classification": inventory["categories"].get("pending_classification", 0),
        }

        print(json.dumps(report, ensure_ascii=False, indent=2))

        if args.manifest:
            with open(args.manifest, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\nManifest written to {args.manifest}")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
