"""Event Extraction (Phase 11).

مسیر: چند Article مرتبط (خوشه‌ی dedup) → یک Event واحد.

- گروه‌بندی بر اساس `duplicate_cluster` (خوشه‌ی dedup) یا `event_cluster`.
- استخراج فیلدهای Event با AI Gateway (structured JSON).
- اگر خوشه تک‌مقاله باشد، یک Event سبک از خود مقاله ساخته می‌شود (بدون AI).
- ID رویداد deterministic نیست اما اتصال مقاله↔رویداد ثبت می‌شود.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.event import Event
from domains.events.prompts import EVENT_SCHEMA, EXTRACT_EVENT

logger = get_logger(__name__)

MAX_ARTICLES_PER_EVENT = 8


@dataclass
class EventOutcome:
    events_created: int = 0
    articles_linked: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _iso_or_none(value: object) -> str | None:
    if not value:
        return None
    return str(value)


class EventExtractor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    def _pending_clusters(self, *, limit: int) -> list[tuple[str, list[Article]]]:
        """خوشه‌های مقالاتی که هنوز به هیچ Event وصل نشده‌اند."""
        stmt = (
            select(Article)
            .where(Article.event_id.is_(None))
            .where(Article.classification_status == "done")
            .order_by(Article.retrieved_at.desc().nullslast())
            .limit(limit * MAX_ARTICLES_PER_EVENT)
        )
        articles = list(self.db.execute(stmt).scalars().all())

        clusters: dict[str, list[Article]] = {}
        for a in articles:
            key = a.duplicate_cluster or f"single:{a.id}"
            clusters.setdefault(key, []).append(a)
        return list(clusters.items())[:limit]

    async def extract_event_from_cluster(self, articles: list[Article]) -> Event | None:
        """از یک خوشه‌ی مقالات، یک Event می‌سازد."""
        if not articles:
            return None

        # متن ترکیبی برای AI
        joined = "\n\n---\n\n".join(
            f"[{i+1}] {(a.title or '')}\n{a.summary or ''}"
            for i, a in enumerate(articles[:MAX_ARTICLES_PER_EVENT])
        )

        data: dict = {}
        confidence = None
        used_ai = False
        try:
            prompt = EXTRACT_EVENT.render(articles=joined[:8000])
            request = AIRequest(
                messages=[
                    Message.system("You output strict JSON compatible with the schema."),
                    Message.user(prompt),
                ],
                role="deep_analysis",
                task="extract_event",
                temperature=0.1,
                json_schema=EVENT_SCHEMA,
                metadata={"prompt_version": EXTRACT_EVENT.version},
            )
            response = await self.gateway.structured_generate(request, EVENT_SCHEMA)
            if response.is_mock and not self._settings.mock_mode:
                raise ValueError("mock event rejected in production mode")
            data = response.structured or _safe_json(response.text) or {}
            confidence = data.get("confidence")
            used_ai = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("event extraction failed, fallback to lightweight | err=%s", exc)

        # Event را بساز
        source_ids = sorted({str(a.document.source_id) for a in articles if a.document and a.document.source_id})
        event = Event(
            event_type=data.get("event_type") or (articles[0].topics and _first_topic(articles[0])) or "unknown",
            occurred_at=_parse_dt(data.get("occurred_at"))
            or min((a.published_at for a in articles if a.published_at), default=None),
            location=data.get("location"),
            actors=json.dumps(data.get("actors") or [], ensure_ascii=False),
            action=data.get("action") or (articles[0].title or None),
            expected=data.get("expected"),
            actual=data.get("actual"),
            surprise=data.get("surprise"),
            affected_assets=json.dumps(data.get("affected_assets") or [], ensure_ascii=False),
            affected_indicators=json.dumps(data.get("affected_indicators") or [], ensure_ascii=False),
            sources=json.dumps(source_ids, ensure_ascii=False),
            confidence=confidence if isinstance(confidence, (int, float)) else None,
            published_at=min((a.published_at for a in articles if a.published_at), default=None),
            retrieved_at=datetime.now(UTC),
            available_at=datetime.now(UTC),
            observed_at=datetime.now(UTC),
        )
        self.db.add(event)
        self.db.flush()

        # اتصال مقالات به رویداد
        cluster_id = str(event.id)
        for a in articles:
            a.event_id = event.id
            a.event_cluster = cluster_id

        event.event_metadata = json.dumps({"used_ai": used_ai, "article_count": len(articles)})
        return event

    async def run(self, *, limit: int = 50) -> EventOutcome:
        outcome = EventOutcome()
        clusters = self._pending_clusters(limit=limit)
        for _, articles in clusters:
            try:
                event = await self.extract_event_from_cluster(articles)
                if event is None:
                    continue
                outcome.events_created += 1
                outcome.articles_linked += len(articles)
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("event cluster failed | err=%s", exc)
            self.db.commit()
        logger.info(
            "event extraction done | events=%d linked=%d failed=%d",
            outcome.events_created, outcome.articles_linked, outcome.failed,
        )
        return outcome


def _first_topic(article: Article) -> str | None:
    try:
        topics = json.loads(article.topics or "[]")
        return topics[0] if topics else None
    except Exception:  # noqa: BLE001
        return None


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:  # noqa: BLE001
        return None


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
