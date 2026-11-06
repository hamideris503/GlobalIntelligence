"""Inbox queries and KPIs (stage 5).

A read-only view over classified articles: each item joins the article, its
document (priority/source) and the persisted screening outcome. ``evidence_status``
is derived, never stored, and is ``null`` when it cannot be computed.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.ai.local_screening import review
from backend.database.models.article import Article
from backend.database.models.document import Document

MAX_PAGE_SIZE = 100

SortField = Literal["retrieved_at", "priority", "title"]
SORTABLE = ("retrieved_at", "priority", "title")

_EVIDENCE_MIN_SOURCES = 2


def _parse_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _evidence_status(article: Article) -> str | None:
    """Derived evidence state; ``null`` when it cannot be computed.

    - ``none``: classification not done yet.
    - ``thin``: done but no linked event/claims.
    - ``supported``: linked to an event (single-source evidence).
    """
    if article.classification_status != "done":
        return None
    if article.event_id is None:
        return "thin"
    return "supported"


def _domain(article: Article) -> str | None:
    meta = review.parse_meta(article.classification_meta)
    routing = meta.get("domain_routing")
    if isinstance(routing, dict):
        domains = routing.get("domains")
        if isinstance(domains, list) and domains:
            return str(domains[0])
    topics = _parse_list(article.topics)
    return str(topics[0]) if topics else None


def _item(article: Article, document: Document | None) -> dict[str, Any]:
    meta = review.parse_meta(article.classification_meta)
    state = review.review_state(meta, article.classification_status)
    return {
        "article_id": str(article.id),
        "title": article.title or (document.title if document else None),
        "source_name": article.source_name,
        "priority": document.ingestion_priority if document else None,
        "domain": _domain(article),
        "analysis_status": article.classification_status,
        "duplicate_cluster_id": article.duplicate_cluster,
        "screening_status": state["screening_status"],
        "evidence_status": _evidence_status(article),
        "retrieved_at": article.retrieved_at.isoformat() if article.retrieved_at else None,
        "review_required": state["review_required"],
    }


def _base_stmt():
    return select(Article, Document).outerjoin(Document, Article.document_id == Document.id)


def inbox_page(
    db: Session,
    *,
    q: str | None = None,
    priority: str | None = None,
    domain: str | None = None,
    analysis_status: str | None = None,
    dedup_state: str | None = None,
    screening_status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "-retrieved_at",
) -> dict[str, Any]:
    direction = "desc" if sort.startswith("-") else "asc"
    field = sort.lstrip("-")
    if field not in SORTABLE:
        field = "retrieved_at"
        direction = "desc"

    stmt = _base_stmt()
    if priority:
        stmt = stmt.where(func.upper(Document.ingestion_priority) == priority.upper())
    if analysis_status:
        stmt = stmt.where(Article.classification_status == analysis_status)
    if dedup_state == "duplicate":
        stmt = stmt.where(Article.duplicate_cluster.is_not(None))
    elif dedup_state == "unique":
        stmt = stmt.where(Article.duplicate_cluster.is_(None))
    if screening_status:
        if screening_status == "missing":
            stmt = stmt.where(
                ~review._contains('"local_screening"'), ~review._contains('"skipped_ai"')
            )
        else:
            stmt = stmt.where(review._screening_clause(screening_status))
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Article.title.ilike(needle), Article.source_name.ilike(needle)))

    order_col = {
        "retrieved_at": Article.retrieved_at,
        "priority": Document.ingestion_priority,
        "title": Article.title,
    }[field]
    order = order_col.desc() if direction == "desc" else order_col.asc()
    stmt = stmt.order_by(order, Article.id.desc())

    rows = db.execute(
        stmt.limit(page_size + 1).offset((page - 1) * page_size)
    ).all()
    has_more = len(rows) > page_size
    items = [_item(a, d) for a, d in rows[:page_size]]
    if domain:
        items = [i for i in items if i["domain"] == domain]
    total = int(
        db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def inbox_summary(db: Session) -> dict[str, Any]:
    """KPIs with explicit definitions (each count states its rule)."""
    total = int(db.execute(select(func.count()).select_from(Article)).scalar_one() or 0)

    p0_p1 = int(
        db.execute(
            select(func.count())
            .select_from(Article)
            .join(Document, Article.document_id == Document.id)
            .where(func.upper(Document.ingestion_priority).in_(("P0", "P1")))
        ).scalar_one() or 0
    )

    needs_screening = int(
        db.execute(
            select(func.count()).select_from(Article).where(
                review.review_clause(),
                ~review._contains('"decision": true'),
            )
        ).scalar_one() or 0
    )

    duplicate_candidates = int(
        db.execute(
            select(func.count()).select_from(Article).where(
                Article.duplicate_cluster.is_not(None)
            )
        ).scalar_one() or 0
    )

    # evidence "insufficient": classification done but no event linked (thin)
    thin = int(
        db.execute(
            select(func.count()).select_from(Article).where(
                Article.classification_status == "done", Article.event_id.is_(None)
            )
        ).scalar_one() or 0
    )

    return {
        "total_articles": total,
        "p0_p1_new": p0_p1,
        "needs_screening": needs_screening,
        "duplicate_candidates": duplicate_candidates,
        "insufficient_evidence": thin,
        "definitions": {
            "p0_p1_new": "articles whose document ingestion_priority is P0 or P1",
            "needs_screening": "review-required articles without a true screening decision",
            "duplicate_candidates": "articles with a non-null duplicate_cluster",
            "insufficient_evidence": "classification done but no linked event",
        },
    }
