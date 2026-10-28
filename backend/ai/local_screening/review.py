"""Operational review queue over persisted screening outcomes (Stage91).

No schema change. Eligibility is derived from what a screen already persisted
(``Article.classification_meta`` + ``classification_status``); an explicit
acknowledgement is written under ``classification_meta["human_review"]`` and
never touches the automated decision.

Queries use only portable SQL: JSON is read in Python, and the SQL prefilter
matches fixed markers in the TEXT column with ``LIKE`` (works on SQLite and
PostgreSQL). Markers and Python reason codes come from the same constants, so
a page never disagrees with the total it is cut from.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from backend.database.models.article import Article
from backend.database.models.document import Document

MAX_PAGE_SIZE = 100
MAX_NOTE = 500
_MAX_ACK_TRIES = 3

ScreeningStatus = Literal[
    "missing", "skipped", "pending", "failed", "relevant", "not_relevant"
]

# Codes that mean "the automated answer is not a trustworthy full-input
# decision". Success codes (``*_RELEVANT``, ``AI_FALLBACK``, ``LOCAL_DISABLED``)
# are absent on purpose: a usable decision was produced.
REVIEW_CODES = frozenset({
    "AI_ABSTAINED", "AI_UNAVAILABLE", "EMPTY_INPUT", "UNSUPPORTED_LANGUAGE",
    "P0_P1_SAFEGUARD", "PRIORITY_REVIEW", "DISAGREEMENT",
    "LOW_MARGIN", "KEV_LOW_MARGIN", "LAYA_LOW_MARGIN",
    "KEV_INPUT_TOO_LONG", "LAYA_INPUT_TOO_LONG",
    "KEV_TRUNCATED", "LAYA_TRUNCATED",
    "KEV_TOO_LONG", "LAYA_TOO_LONG",
    "KEV_UNAVAILABLE", "LAYA_UNAVAILABLE",
    "KEV_ERROR", "LAYA_ERROR",
    "KEV_NO_RESULT", "LAYA_NO_RESULT",
    "KEV_INVALID_OUTPUT", "LAYA_INVALID_OUTPUT",
    "KEV_UNSUPPORTED_LANGUAGE", "LAYA_UNSUPPORTED_LANGUAGE",
})
REVIEW_PREFIXES = ("AI_ERROR", "PAIR_INVALID", "SCREENING_EXCEPTION")


def parse_meta(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def screening_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    value = meta.get("local_screening")
    return value if isinstance(value, dict) else None


def screening_status(meta: dict[str, Any], classification_status: str | None) -> str:
    if classification_status == "failed":
        return "failed"
    screening = screening_meta(meta)
    if screening is None:
        return "skipped" if meta.get("skipped_ai") else "missing"
    decision = screening.get("decision")
    if decision is True:
        return "relevant"
    if decision is False:
        return "not_relevant"
    return "pending"


def _is_review_code(code: str) -> bool:
    return code in REVIEW_CODES or code.split(":", 1)[0] in REVIEW_PREFIXES


def review_reasons(meta: dict[str, Any], classification_status: str | None) -> list[str]:
    """Every persisted reason this record needs a human look; priority alone never is."""
    reasons: list[str] = []
    if classification_status == "failed":
        reasons.append("CLASSIFICATION_FAILED")
    elif classification_status != "done":
        reasons.append("CLASSIFICATION_PENDING")

    screening = screening_meta(meta)
    if screening is not None:
        for code in screening.get("reason_codes") or []:
            code = str(code)
            if _is_review_code(code) and code not in reasons:
                reasons.append(code)
        if screening.get("p0_p1_safeguard") is True and "P0_P1_SAFEGUARD" not in reasons:
            reasons.append("P0_P1_SAFEGUARD")
        if screening.get("decision") is None and "SCREENING_PENDING" not in reasons:
            reasons.append("SCREENING_PENDING")
    return reasons


def review_state(
    meta: dict[str, Any], classification_status: str | None,
) -> dict[str, Any]:
    review = meta.get("human_review")
    review = review if isinstance(review, dict) else {}
    reasons = review_reasons(meta, classification_status)
    return {
        "screening_status": screening_status(meta, classification_status),
        "review_required": bool(reasons),
        "review_reasons": reasons,
        "review_acknowledged": review.get("acknowledged") is True,
        "acknowledged_at": review.get("acknowledged_at"),
    }


# --- portable SQL prefilter -------------------------------------------------

# json.dumps uses the default separators (": " and ", "), so these markers are
# exact for every stored screening written by the project. SQLite compares LIKE
# case-insensitively, so P0_P1_SAFEGUARD is matched by its boolean field
# instead of its code (the two are always written together).
_MARKERS = tuple(
    f'"{code}"' for code in sorted(REVIEW_CODES - {"P0_P1_SAFEGUARD"})
) + tuple(
    f'"{prefix}:' for prefix in REVIEW_PREFIXES
) + ('"p0_p1_safeguard": true', '"decision": null')


def _contains(fragment: str):
    """Exact substring match; ``_``/``%`` are escaped so codes match literally."""
    escaped = fragment.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return Article.classification_meta.like(f"%{escaped}%", escape="\\")


def review_clause():
    """SQL prefilter for review-required rows using the same codes as Python."""
    markers = or_(*[_contains(m) for m in _MARKERS])
    return or_(
        Article.classification_status.is_(None),
        Article.classification_status != "done",
        markers,
    )


def _screening_clause(status: str):
    if status == "failed":
        return Article.classification_status == "failed"
    return {
        "skipped": _contains('"skipped_ai"'),
        "pending": _contains('"decision": null'),
        "relevant": _contains('"decision": true'),
        "not_relevant": _contains('"decision": false'),
    }[status]


def _ack_clause(acknowledged: bool):
    marker = _contains('"acknowledged": true')
    return marker if acknowledged else ~marker


def queue_page(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    review_required: bool = True,
    p0_p1: bool = False,
    acknowledged: bool | None = None,
    screening: str | None = None,
) -> dict[str, Any]:
    """One bounded page of the review queue (or, with review_required=False,
    of the non-flagged screening outcomes)."""
    stmt = (
        select(Article, Document)
        .outerjoin(Document, Article.document_id == Document.id)
        .where(
            review_clause() if review_required else ~review_clause(),
        )
    )
    if screening is not None:
        if screening == "missing":
            stmt = stmt.where(
                ~_contains('"local_screening"'),
                ~_contains('"skipped_ai"'),
            )
        else:
            stmt = stmt.where(_screening_clause(screening))
    if p0_p1:
        stmt = stmt.where(func.upper(Document.ingestion_priority).in_(("P0", "P1")))
    if acknowledged is not None:
        stmt = stmt.where(_ack_clause(acknowledged))

    rows = db.execute(
        stmt.order_by(
            Article.retrieved_at.desc().nullslast(), Article.id.desc()
        ).limit(page_size + 1).offset((page - 1) * page_size)
    ).all()
    has_more = len(rows) > page_size
    items = [_item(article, document) for article, document in rows[:page_size]]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def _item(article: Article, document: Document | None) -> dict[str, Any]:
    meta = parse_meta(article.classification_meta)
    state = review_state(meta, article.classification_status)
    routing = meta.get("domain_routing")
    routing = routing if isinstance(routing, dict) else None
    return {
        "article_id": str(article.id),
        "title": article.title or (document.title if document else None),
        "article_url": (document.url or document.canonical_url) if document else None,
        "source_name": article.source_name,
        "priority": document.ingestion_priority if document else None,
        "priority_source": document.priority_source if document else None,
        "classification_status": article.classification_status,
        "classification_error": article.classification_error,
        "retrieved_at": _iso(article.retrieved_at),
        "screening": screening_meta(meta),
        "domains": (routing or {}).get("domains"),
        "domain_state": (routing or {}).get("state"),
        **state,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# --- durable acknowledgement ------------------------------------------------

class ReviewNotFound(LookupError):
    pass


class ReviewConflict(RuntimeError):
    pass


def acknowledge(
    db: Session, article_id: uuid.UUID, *, note: str | None = None,
) -> dict[str, Any]:
    """Add ``human_review`` beside the automated result, idempotently.

    Compare-and-set on the raw TEXT keeps a concurrent classifier write intact:
    the update only lands if nobody else changed ``classification_meta``.
    """
    note = (note or "").strip()[:MAX_NOTE]
    for _ in range(_MAX_ACK_TRIES):
        article = db.get(Article, article_id)
        if article is None:
            raise ReviewNotFound(str(article_id))
        raw = article.classification_meta
        meta = parse_meta(raw)
        existing = meta.get("human_review")
        if isinstance(existing, dict) and existing.get("acknowledged") is True:
            return {
                **_item(article, article.document),
                "already_acknowledged": True,
                "human_review": existing,
            }

        reasons = review_reasons(meta, article.classification_status)
        review = {
            "acknowledged": True,
            "acknowledged_at": datetime.now(UTC).isoformat(),
            "actor": "api_key",
            "note": note,
            "screening_decision": (
                screening_meta(meta) or {}
            ).get("decision"),
            "review_reasons": reasons,
        }
        meta["human_review"] = review
        new_raw = json.dumps(meta, ensure_ascii=False)
        stmt = update(Article).where(Article.id == article_id)
        stmt = stmt.where(
            Article.classification_meta.is_(None) if raw is None
            else Article.classification_meta == raw
        )
        result = db.execute(stmt.values(classification_meta=new_raw))
        db.commit()
        if (result.rowcount or 0) == 1:
            db.expire(article)
            fresh = db.get(Article, article_id)
            return {
                **_item(fresh, fresh.document),
                "already_acknowledged": False,
                "human_review": review,
            }
        db.expire_all()
    raise ReviewConflict("article review state changed concurrently; retry")
