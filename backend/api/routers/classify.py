"""Article Classification API (Phase 10)."""
from __future__ import annotations

import json
import uuid

from domains.news.classifier import ArticleClassifier
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.schemas.ingestion import PriorityLevel
from backend.database.models.article import Article
from backend.database.session import get_db

router = APIRouter(prefix="/api/classify", tags=["classification"])


class ClassifyOutcomeRead(BaseModel):
    classified: int
    failed: int
    # موارد کنارگذاشته‌شده در همان اجرا (گیت اولویت، بودجه/سهمیه، محافظ mock در prod)
    skipped: int = 0
    errors: list[str]


@router.post("/run", response_model=ClassifyOutcomeRead)
async def run_classify(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> ClassifyOutcomeRead:
    """طبقه‌بندی مقالاتی که هنوز topics ندارند."""
    outcome = await ArticleClassifier(db).classify_pending(limit=limit)
    return ClassifyOutcomeRead(
        classified=outcome.classified,
        failed=outcome.failed,
        skipped=outcome.skipped,
        errors=outcome.errors,
    )


class ArticleClassifiedRead(BaseModel):
    id: str
    title: str | None
    topics: list[str]
    entities: list[dict]
    sentiment: float | None
    stance: str | None
    importance: int | None
    decided_by: str | None = None
    confidence: float | None
    # Ingest priority of the underlying document (P0..P4) — separate from the
    # analytic `importance`; without it the triage view cannot show P0..P4.
    priority: PriorityLevel | None = None


class ArticleDetailRead(ArticleClassifiedRead):
    summary: str | None = None
    language: str | None = None
    country: str | None = None
    source_name: str | None = None
    url: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    event_id: str | None = None
    classification_status: str | None = None
    classification_error: str | None = None
    provider: str | None = None
    is_mock: bool | None = None


@router.get("/articles", response_model=list[ArticleClassifiedRead])
def list_classified(
    limit: int = Query(default=50, ge=1, le=500),
    only_classified: bool = True,
    db: Session = Depends(get_db),
) -> list[ArticleClassifiedRead]:
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from backend.database.models.article import Article

    stmt = (
        select(Article)
        .options(joinedload(Article.document))  # priority lives on the document
        .order_by(Article.retrieved_at.desc().nullslast())
        .limit(limit)
    )
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
            decided_by=a.decided_by,
            confidence=a.confidence,
            priority=a.document.ingestion_priority if a.document else None,
        )
        for a in rows
    ]


@router.get("/articles/{article_id}", response_model=ArticleDetailRead)
def get_article(article_id: uuid.UUID, db: Session = Depends(get_db)) -> ArticleDetailRead:
    """جزئیات کامل یک مقاله (برای صفحهٔ جزئیات خبر)."""
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    doc = article.document
    meta: dict = {}
    try:
        meta = json.loads(article.classification_meta or "{}")
    except Exception:  # noqa: BLE001
        meta = {}
    return ArticleDetailRead(
        id=str(article.id),
        title=article.title,
        topics=_parse_list(article.topics),
        entities=_parse_list(article.entities),
        sentiment=article.sentiment,
        stance=article.stance,
        importance=article.importance,
        decided_by=article.decided_by,
        confidence=article.confidence,
        priority=doc.ingestion_priority if doc is not None else None,
        summary=article.summary,
        language=article.language,
        country=article.country,
        source_name=article.source_name,
        url=doc.url if doc is not None else None,
        published_at=doc.published_at.isoformat() if doc is not None and doc.published_at else None,
        retrieved_at=article.retrieved_at.isoformat() if article.retrieved_at else None,
        event_id=str(article.event_id) if article.event_id else None,
        classification_status=article.classification_status,
        classification_error=article.classification_error,
        provider=meta.get("provider"),
        is_mock=meta.get("is_mock"),
    )


def _parse_list(value: str | None) -> list:
    if not value:
        return []
    try:
        out = json.loads(value)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []
