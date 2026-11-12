"""Human decision recording (stage 5).

Append-only: each decision is a new ``human_reviews`` row. It never rewrites the
automated screening/classification output. An ``ack`` also keeps writing the
legacy ``classification_meta["human_review"]`` marker so existing consumers keep
working; the other actions are persisted only in ``human_reviews``.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.local_screening import review as screening_review
from backend.database.models.article import Article
from backend.database.models.human_review import REVIEW_ACTIONS, HumanReview

MAX_NOTE = 500


class ReviewEntityNotFound(LookupError):
    pass


class ReviewActionInvalid(ValueError):
    pass


def record_decision(
    db: Session,
    entity_id: uuid.UUID,
    *,
    action: str,
    actor: str,
    actor_user_id: uuid.UUID | None = None,
    note: str | None = None,
    entity_type: str = "article",
) -> dict[str, Any]:
    if action not in REVIEW_ACTIONS:
        raise ReviewActionInvalid(action)
    entity = db.get(Article, entity_id) if entity_type == "article" else None
    if entity_type == "article" and entity is None:
        raise ReviewEntityNotFound(str(entity_id))

    row = HumanReview(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor[:128],
        actor_user_id=actor_user_id,
        note=(note or "").strip()[:MAX_NOTE] or None,
    )
    db.add(row)
    db.flush()

    # ack keeps the legacy marker for existing consumers; others are additive only.
    if action == "ack" and entity_type == "article":
        try:
            screening_review.acknowledge(db, entity_id, note=note)
        except (screening_review.ReviewNotFound, screening_review.ReviewConflict):
            pass

    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "action": row.action,
        "actor": row.actor,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def history(
    db: Session, entity_id: uuid.UUID, *, entity_type: str = "article"
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(HumanReview)
        .where(HumanReview.entity_type == entity_type, HumanReview.entity_id == entity_id)
        .order_by(HumanReview.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "actor": r.actor,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
