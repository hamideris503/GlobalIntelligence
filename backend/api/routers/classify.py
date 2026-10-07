"""Article Classification API (Phase 10)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db
from domains.news.classifier import ArticleClassifier

router = APIRouter(prefix="/api/classify", tags=["classification"])


class ClassifyOutcomeRead(BaseModel):
    classified: int
    failed: int
    errors: list[str]


@router.post("/run", response_model=ClassifyOutcomeRead)
async def run_classify(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> ClassifyOutcomeRead:
    """طبقه‌بندی مقالاتی که هنوز topics ندارند."""
    outcome = await ArticleClassifier(db).classify_pending(limit=limit)
    return ClassifyOutcomeRead(
        classified=outcome.classified, failed=outcome.failed, errors=outcome.errors
    )


class ArticleClassifiedRead(BaseModel):
    id: str
    title: str | None
    topics: list[str]
    entities: list[dict]
    sentiment: float | None
    stance: str | None
    importance: int | None
    confidence: float | None


@router.get("/articles", response_model=list[ArticleClassifiedRead])
def list_classified(
    limit: int = Query(default=50, ge=1, le=500),
    only_classified: bool = True,
    db: Session = Depends(get_db),
) -> list[ArticleClassifiedRead]:
    from sqlalchemy import select

    from backend.database.models.article import Article

    stmt = select(Article).order_by(Article.retrieved_at.desc().nullslast()).limit(limit)
    if only_classified:
        stmt = stmt.where(Article.topics.is_not(None))
    rows = db.execute(stmt).scalars().all()
    return [
        ArticleClassifiedRead(
            id=str(a.id),
            title=a.title,
            topics=_parse_list(a.topics),
            entities=_parse_list(a.entities),
            sentiment=a.sentiment,
            stance=a.stance,
            importance=a.importance,
            confidence=a.confidence,
        )
        for a in rows
    ]


def _parse_list(value: str | None) -> list:
    if not value:
        return []
    try:
        out = json.loads(value)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []
